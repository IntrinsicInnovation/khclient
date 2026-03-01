using System.ComponentModel.DataAnnotations;

namespace KhServer.Models
{
    public class Found
    {
        [Key]
        public int Id { get; set; }
        public long Datetime { get; set; }
        public string? WorkerId { get; set; }
        public string? PrivateKey { get; set; }
    }
}