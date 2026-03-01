using System.Text.Json.Serialization;

namespace KhServer.DTOs
{
    public class LeaseRequest
    {
        [JsonPropertyName("workerId")]
        public string WorkerId { get; set; } = string.Empty;
    }
}