using System.Text.Json;
using STS2Connector.LiveHost;

// Invoke the compiled production field projections on saved source vectors.
// No game is started; native effects and historical captures are unchanged.
var input = JsonDocument.Parse(Console.In.ReadToEnd());
var rows = new List<object?>();
foreach (var row in input.RootElement.EnumerateArray())
{
    switch (row.GetProperty("kind").GetString())
    {
        case "event":
            rows.Add(EventOptionSurfaceReader.IsOptionEnabled(row.GetProperty("button_enabled").GetBoolean(), row.GetProperty("locked").GetBoolean()));
            break;
        case "counter":
            rows.Add(VisibleEntityFacts.VisibleCounter(row.GetProperty("inventory_renderer").GetBoolean(), row.GetProperty("show_counter").GetBoolean(), () => row.GetProperty("amount").GetInt32()));
            break;
        default:
            throw new InvalidOperationException("Unknown saved/source vector.");
    }
}
Console.WriteLine(JsonSerializer.Serialize(rows));
