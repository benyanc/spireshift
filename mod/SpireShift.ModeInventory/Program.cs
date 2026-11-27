// Read metadata and IL bytes only. Never load or execute the inspected assembly.
using System.Reflection;
using System.Reflection.Emit;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

if (args.SequenceEqual(new[] { "--self-test" }))
{
    try
    {
        Inventory.SelfTest();
        Console.WriteLine("Mode-reference decoder and synthetic assembly checks passed.");
        return 0;
    }
    catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
}
if (args.Length != 4 || args[0] != "--assembly" || args[2] != "--output")
{
    Console.Error.WriteLine("Use --assembly PATH --output PRIVATE_JSON, or --self-test.");
    return 2;
}
try
{
    var result = Inventory.Scan(args[1], new HashSet<string>(StringComparer.Ordinal)
    {
        "MegaCrit.Sts2.Core.TestSupport.TestMode",
        "MegaCrit.Sts2.Core.Helpers.NonInteractiveMode"
    });
    using var output = new FileStream(args[3], FileMode.CreateNew, FileAccess.Write);
    JsonSerializer.Serialize(output, result, new JsonSerializerOptions { WriteIndented = true });
    return 0;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.Message);
    return 1;
}

internal static class Inventory
{
    private static readonly Dictionary<ushort, OpCode> Codes = typeof(OpCodes).GetFields()
        .Where(field => field.FieldType == typeof(OpCode))
        .Select(field => (OpCode)field.GetValue(null)!)
        .Where(code => code.Name is not null && !code.Name.StartsWith("prefix", StringComparison.Ordinal))
        .ToDictionary(code => unchecked((ushort)code.Value));

    internal readonly record struct Instruction(int Offset, string Name, int? Token);

    internal static List<Instruction> Decode(byte[] bytes)
    {
        var result = new List<Instruction>();
        int offset = 0;
        while (offset < bytes.Length)
        {
            int start = offset;
            ushort value = bytes[offset++];
            if (value == 0xfe)
            {
                if (offset == bytes.Length) throw new BadImageFormatException("Truncated IL opcode");
                value = (ushort)(0xfe00 | bytes[offset++]);
            }
            if (!Codes.TryGetValue(value, out var code))
                throw new BadImageFormatException($"Unknown IL opcode at {start}");
            int size = code.OperandType switch
            {
                OperandType.InlineNone => 0,
                OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar => 1,
                OperandType.InlineVar => 2,
                OperandType.InlineI8 or OperandType.InlineR => 8,
                OperandType.InlineBrTarget or OperandType.InlineField or OperandType.InlineI
                    or OperandType.InlineMethod or OperandType.InlineSig or OperandType.InlineString
                    or OperandType.InlineTok or OperandType.InlineType or OperandType.ShortInlineR => 4,
                OperandType.InlineSwitch => -1,
                _ => throw new BadImageFormatException("Unsupported IL operand type")
            };
            if (size == -1)
            {
                if (bytes.Length - offset < 4) throw new BadImageFormatException("Truncated switch count");
                int count = ReadInt(bytes, offset);
                if (count < 0 || count > (bytes.Length - offset - 4) / 4)
                    throw new BadImageFormatException("Invalid switch table");
                size = checked(4 + count * 4);
            }
            if (bytes.Length - offset < size) throw new BadImageFormatException("Truncated IL operand");
            int? token = code.OperandType is OperandType.InlineMethod or OperandType.InlineField
                or OperandType.InlineType or OperandType.InlineTok ? ReadInt(bytes, offset) : null;
            result.Add(new Instruction(start, code.Name!, token));
            offset += size;
        }
        return result;
    }

    private static int ReadInt(byte[] data, int offset) =>
        System.Buffers.Binary.BinaryPrimitives.ReadInt32LittleEndian(data.AsSpan(offset, 4));

    internal static object Scan(string path, HashSet<string> targets)
    {
        using var input = File.OpenRead(path);
        string hash = Convert.ToHexStringLower(SHA256.HashData(input));
        input.Position = 0;
        using var pe = new PEReader(input, PEStreamOptions.PrefetchEntireImage);
        if (!pe.HasMetadata) throw new BadImageFormatException("A managed assembly is required");
        var md = pe.GetMetadataReader();
        string TypeName(EntityHandle handle) => handle.Kind switch
        {
            HandleKind.TypeDefinition => DefinitionName((TypeDefinitionHandle)handle),
            HandleKind.TypeReference => ReferenceName((TypeReferenceHandle)handle),
            HandleKind.TypeSpecification => "<type-specification>",
            HandleKind.ModuleReference => "<module-reference>",
            HandleKind.MethodDefinition => TypeName(md.GetMethodDefinition((MethodDefinitionHandle)handle).GetDeclaringType()),
            _ => throw new BadImageFormatException($"Unexpected member parent: {handle.Kind}")
        };
        string DefinitionName(TypeDefinitionHandle handle)
        {
            var type = md.GetTypeDefinition(handle);
            return type.GetDeclaringType().IsNil
                ? Join(md.GetString(type.Namespace), md.GetString(type.Name))
                : DefinitionName(type.GetDeclaringType()) + "+" + md.GetString(type.Name);
        }
        string ReferenceName(TypeReferenceHandle handle)
        {
            var type = md.GetTypeReference(handle);
            return type.ResolutionScope.Kind == HandleKind.TypeReference
                ? ReferenceName((TypeReferenceHandle)type.ResolutionScope) + "+" + md.GetString(type.Name)
                : Join(md.GetString(type.Namespace), md.GetString(type.Name));
        }
        (string Type, string Member)? Resolve(EntityHandle handle)
        {
            if (handle.Kind == HandleKind.MethodSpecification)
                return Resolve(md.GetMethodSpecification((MethodSpecificationHandle)handle).Method);
            if (handle.Kind == HandleKind.MemberReference)
            {
                var member = md.GetMemberReference((MemberReferenceHandle)handle);
                return (TypeName(member.Parent), md.GetString(member.Name));
            }
            if (handle.Kind == HandleKind.MethodDefinition)
            {
                var method = md.GetMethodDefinition((MethodDefinitionHandle)handle);
                return (TypeName(method.GetDeclaringType()), md.GetString(method.Name));
            }
            if (handle.Kind == HandleKind.FieldDefinition)
            {
                var field = md.GetFieldDefinition((FieldDefinitionHandle)handle);
                return (TypeName(field.GetDeclaringType()), md.GetString(field.Name));
            }
            if (handle.Kind is HandleKind.TypeDefinition or HandleKind.TypeReference or HandleKind.TypeSpecification)
                return (TypeName(handle), "<type-reference>");
            throw new BadImageFormatException($"Unexpected IL metadata token: {handle.Kind}");
        }
        var sites = new List<object>();
        int methods = 0, bodies = 0, instructions = 0;
        foreach (var handle in md.MethodDefinitions)
        {
            methods++;
            var method = md.GetMethodDefinition(handle);
            if (method.RelativeVirtualAddress == 0) continue;
            bodies++;
            var bytes = pe.GetMethodBody(method.RelativeVirtualAddress).GetILBytes() ?? [];
            var decoded = Decode(bytes);
            instructions += decoded.Count;
            foreach (var op in decoded.Where(row => row.Token.HasValue))
            {
                var target = Resolve(MetadataTokens.EntityHandle(op.Token!.Value));
                if (target is null || !targets.Contains(target.Value.Type)) continue;
                sites.Add(new
                {
                    method_token = MetadataTokens.GetToken(handle),
                    declaring_type = TypeName(method.GetDeclaringType()),
                    method = md.GetString(method.Name),
                    signature_sha256 = Hash(md.GetBlobBytes(method.Signature)),
                    method_il_sha256 = Hash(bytes),
                    il_offset = op.Offset,
                    opcode = op.Name,
                    target_type = target.Value.Type,
                    target_member = target.Value.Member
                });
            }
        }
        return new
        {
            schema_version = "managed-mode-reference-inventory-v1",
            assembly_sha256 = hash,
            module_mvid = md.GetGuid(md.GetModuleDefinition().Mvid).ToString("D"),
            target_types = targets.Order().ToArray(),
            type_definitions = md.TypeDefinitions.Count,
            methods,
            method_bodies = bodies,
            decoded_instructions = instructions,
            undecoded_bodies = 0,
            sites,
            scope = "all_direct_metadata_and_IL_references_to_two_exact_mode_types_not_reflection_or_full_behavior",
            game_assembly_executed = false
        };
    }

    private static string Join(string ns, string name) => ns.Length == 0 ? name : ns + "." + name;
    private static string Hash(byte[] bytes) => Convert.ToHexStringLower(SHA256.HashData(bytes));

    internal static void SelfTest()
    {
        void Require(bool ok) { if (!ok) throw new Exception("Mode inventory self-test failed"); }
        // Token-shaped bytes in a string operand, integer and switch table are not references.
        Require(Decode([0x72, 0x28, 0x01, 0x00, 0x06, 0x20, 0x28, 0x01, 0x00, 0x06,
            0x45, 0x01, 0x00, 0x00, 0x00, 0x28, 0x01, 0x00, 0x06, 0x2a]).All(row => row.Token is null));
        Require(Decode([0xfe, 0x16, 0x01, 0x00, 0x00, 0x01, 0x2a])[0].Token == 0x01000001);
        foreach (var invalid in new byte[][] { [0xfe], [0x28, 0], [0x45, 0xff, 0xff, 0xff, 0x7f], [0xff] })
        {
            bool rejected = false;
            try { Decode(invalid); } catch (BadImageFormatException) { rejected = true; }
            Require(rejected);
        }
        var json = JsonSerializer.SerializeToElement(Scan(typeof(Inventory).Assembly.Location,
            new HashSet<string> { "SyntheticMode" }));
        var sites = json.GetProperty("sites").EnumerateArray().ToArray();
        Require(sites.Any(row => row.GetProperty("target_member").GetString() == "get_IsOn"));
        Require(sites.Any(row => row.GetProperty("declaring_type").GetString()!.Contains("d__")));
        Require(!sites.Any(row => row.GetProperty("method").GetString() == nameof(SyntheticMode.Literal)));
    }
}

internal static class SyntheticMode
{
    internal static bool IsOn { get; set; }
    internal static string Literal() => "SyntheticMode.IsOn";
    internal static int Read() => IsOn ? 1 : 0;
    internal static async Task<bool> ReadAsync() { await Task.Yield(); return IsOn; }
}
