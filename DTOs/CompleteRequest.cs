using System.Text.Json.Serialization;

namespace KhServer.DTOs
{
    public class CompleteRequest
    {
        [JsonPropertyName("chunkId")]
        public int ChunkId { get; set; }
        [JsonPropertyName("workerId")]
        public string WorkerId { get; set; } = string.Empty;
    }
}