using System.Text;
using MegaCrit.Sts2.Core.Saves;

// Fixture-only backend. The native save managers own every serialized value.
internal sealed class DirectorySaveStore(string directory) : ISaveStore
{
    private readonly string root = Path.GetFullPath(directory);

    public string GetFullPath(string path)
    {
        var full = Path.GetFullPath(path, root);
        if (full != root && !full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new InvalidOperationException("Save path escaped the fixture directory");
        return full;
    }

    public string? ReadFile(string path) => FileExists(path) ? File.ReadAllText(GetFullPath(path)) : null;
    public Task<string?> ReadFileAsync(string path) => Task.FromResult(ReadFile(path));
    public void WriteFile(string path, string content) => WriteFile(path, Encoding.UTF8.GetBytes(content));
    public void WriteFile(string path, byte[] content)
    {
        var target = GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        var temporary = target + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllBytes(temporary, content);
        File.Move(temporary, target, overwrite: true);
    }

    public Task WriteFileAsync(string path, string content) => WriteFileAsync(path, Encoding.UTF8.GetBytes(content));
    public Task WriteFileAsync(string path, byte[] content)
    {
        WriteFile(path, content);
        return Task.CompletedTask;
    }

    public bool FileExists(string path) => File.Exists(GetFullPath(path));
    public bool DirectoryExists(string path) => Directory.Exists(GetFullPath(path));
    public void DeleteFile(string path) => File.Delete(GetFullPath(path));
    public void RenameFile(string sourcePath, string destinationPath) =>
        File.Move(GetFullPath(sourcePath), GetFullPath(destinationPath), overwrite: true);
    public string[] GetFilesInDirectory(string path) => DirectoryExists(path)
        ? Directory.GetFiles(GetFullPath(path)).Select(Path.GetFileName).OfType<string>().ToArray() : [];
    public string[] GetDirectoriesInDirectory(string path) => DirectoryExists(path)
        ? Directory.GetDirectories(GetFullPath(path)).Select(Path.GetFileName).OfType<string>().ToArray() : [];
    public void CreateDirectory(string path) => Directory.CreateDirectory(GetFullPath(path));
    public void DeleteDirectory(string path)
    {
        if (DirectoryExists(path)) Directory.Delete(GetFullPath(path), recursive: true);
    }

    public void DeleteTemporaryFiles(string path)
    {
        foreach (var name in GetFilesInDirectory(path).Where(name => name.EndsWith(".tmp", StringComparison.Ordinal)))
            DeleteFile(Path.Combine(path, name));
    }

    public DateTimeOffset GetLastModifiedTime(string path) => File.GetLastWriteTimeUtc(GetFullPath(path));
    public int GetFileSize(string path) => checked((int)new FileInfo(GetFullPath(path)).Length);
    public void SetLastModifiedTime(string path, DateTimeOffset time) => File.SetLastWriteTimeUtc(GetFullPath(path), time.UtcDateTime);
}
