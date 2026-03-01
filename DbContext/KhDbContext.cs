using KhServer.Models;
using Microsoft.EntityFrameworkCore;

public class KhDbContext : DbContext
{
    public KhDbContext(DbContextOptions<KhDbContext> options) : base(options) { }

    public DbSet<Chunk> Chunks => Set<Chunk>();
    public DbSet<Found> Found => Set<Found>();
}