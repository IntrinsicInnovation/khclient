using System.Text.Json.Serialization;

namespace KhServer.DTOs
{
    public class ReportFoundRequest
    {
        [JsonPropertyName("workerId")]
        public string WorkerId { get; set; } = string.Empty;
        [JsonPropertyName("privateKey")]
        public string PrivateKey { get; set; } = string.Empty;
    }
}