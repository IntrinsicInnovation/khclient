using System.ComponentModel.DataAnnotations;

namespace KhServer.Models
{
    public class Chunk
    {
        [Key]
        public int Id { get; set; }
        public string? Start { get; set; }
        public string? End { get; set; }
        public string? Status { get; set; }
        public string? Worker { get; set; }
        public long Heartbeat { get; set; }
    }
}