using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Mvc;
using KhServer.Models;
using KhServer.DTOs;
using System.Numerics;
using System.Globalization;

var builder = WebApplication.CreateBuilder(args);

// -------------------------
// CONFIG FROM ENVIRONMENT
// -------------------------


var dbHost = "khsql.mysql.database.azure.com"; // Environment.GetEnvironmentVariable("DB_HOST");
var dbUser = "bfdev"; // Environment.GetEnvironmentVariable("DB_USER");
var dbPass = "Irock12!"; // Environment.GetEnvironmentVariable("DB_PASS");
var dbName = "keyhunt"; // Environment.GetEnvironmentVariable("DB_NAME");
var leaseTimeout = TimeSpan.FromHours(3);   // 3 hours
var testRangeSize = 1_000_000_500;

var connectionString = $"server={dbHost};user={dbUser};password={dbPass};database={dbName}";

// -------------------------
// DATABASE CONTEXT
// -------------------------
builder.Services.AddDbContext<KhDbContext>(options =>
    
options.UseMySql(connectionString, ServerVersion.AutoDetect(connectionString))
);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// -------------------------
// HELPERS
// -------------------------
async Task ReclaimExpired(KhDbContext db)
{
    var cutoff = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - (long)leaseTimeout.TotalSeconds;
    await db.Database.ExecuteSqlInterpolatedAsync($@"
        UPDATE chunks
        SET status='pending', worker=NULL
        WHERE status='leased' AND heartbeat < {cutoff};
    ");
}

async Task<int> ReclaimOlderThan(KhDbContext db, int days)
{
    var seconds = days * 24 * 60 * 60;
    var cutoff = DateTimeOffset.UtcNow.ToUnixTimeSeconds() - seconds;
    var affected = await db.Database.ExecuteSqlInterpolatedAsync($@"
        UPDATE chunks
        SET status='pending', worker=NULL
        WHERE status='leased' AND heartbeat < {cutoff};
    ");
    return affected;
}

// -------------------------
// ROUTES
// -------------------------
app.MapGet("/", () => "KeyHunt server running (MySQL)");

app.MapPost("/admin/reset_leases", async ([FromServices] KhDbContext db) =>
{
    var reclaimed = await ReclaimOlderThan(db, 3);
    return Results.Json(new { ok = true, reclaimed });
});






app.MapPost("/lease", async ([FromServices] KhDbContext db, [FromBody] LeaseRequest req) =>
{
    // Fetch one pending chunk from the database
    var chunk = await db.Chunks
        .FromSqlRaw(@"
            SELECT * FROM chunks
            WHERE status IS NULL OR status='pending'
            ORDER BY id
            LIMIT 1
            FOR UPDATE
        ").FirstOrDefaultAsync();

    if (chunk == null)
        return Results.Json(Array.Empty<object>());
    // Strip optional "0x" prefix
    string startHex = chunk.Start.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
        ? chunk.Start[2..]
        : chunk.Start;

    string endHex = chunk.End.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
        ? chunk.End[2..]
        : chunk.End;

    // Use BigInteger for large numbers
    BigInteger chunkStart = BigInteger.Parse(startHex, NumberStyles.HexNumber);
    BigInteger chunkEnd = BigInteger.Parse(endHex, NumberStyles.HexNumber);


    // Calculate lease range
    BigInteger leaseStart = chunkStart;
    BigInteger leaseEnd = BigInteger.Min(chunkStart + testRangeSize - 1, chunkEnd);

    // Update chunk status
    chunk.Status = "leased";
    chunk.Worker = req.WorkerId;
    chunk.Heartbeat = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

    await db.SaveChangesAsync();

    // Return lease info as hex strings
    return Results.Json(new[]
    {
        new {
            chunkId = chunk.Id,
            start = $"0x{leaseStart:X}",
            end = $"0x{leaseEnd:X}"
        }
    });
});


app.MapPost("/heartbeat", async ([FromServices] KhDbContext db, [FromBody] HeartbeatRequest req) =>
{
    var chunk = await db.Chunks.FirstOrDefaultAsync(c => c.Id == req.ChunkId && c.Worker == req.WorkerId);
    if (chunk != null)
    {
        chunk.Heartbeat = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        await db.SaveChangesAsync();
    }
    return Results.Json(new { ok = true });
});

app.MapPost("/complete", async ([FromServices] KhDbContext db, [FromBody] CompleteRequest req) =>
{
    var chunk = await db.Chunks.FirstOrDefaultAsync(c => c.Id == req.ChunkId && c.Worker == req.WorkerId);
    if (chunk != null)
    {
        chunk.Status = "complete";
        await db.SaveChangesAsync();
    }
    return Results.Json(new { ok = true });
});

app.MapPost("/report_found", async ([FromServices] KhDbContext db, [FromBody] ReportFoundRequest req) =>
{
    var found = new Found
    {
        Datetime = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
        WorkerId = req.WorkerId,
        PrivateKey = req.PrivateKey
    };
    db.Found.Add(found);
    await db.SaveChangesAsync();
    return Results.Json(new { ok = true });
});

app.MapGet("/stats", async ([FromServices] KhDbContext db) =>
{
    var total = await db.Chunks.CountAsync();
    var completed = await db.Chunks.CountAsync(c => c.Status == "complete");
    var leased = await db.Chunks.CountAsync(c => c.Status == "leased");
    var pending = await db.Chunks.CountAsync(c => c.Status == "pending");
    var progress = total > 0 ? (double)completed / total * 100 : 0;

    return Results.Json(new
    {
        total,
        completed,
        leased,
        pending,
        progress = Math.Round(progress, 3)
    });
});

// -------------------------
// DASHBOARD (optional)
// -------------------------
app.MapGet("/dashboard", () =>
{
    var html = @"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Keyhunt Dashboard</title>
       
        <style>
            body { font-family: Arial; background:#111; color:#eee; text-align:center; }
            .box { padding:20px; margin:20px auto; width:300px; background:#222; border-radius:10px;}
            h1 { color:#00ffa6; }
            .big { font-size:28px; }
        </style>
    </head>
    <body>
        <h1>Keyhunt Progress Dashboard</h1>

        <button onclick='resetLeases()' 
                style='padding:10px 20px; font-size:16px; margin:15px;
                       background:#ff4444; color:white; border:none; border-radius:8px;'>
            Reset Leases (3+ Days Old)
        </button>

        <div id='stats'>Loading...</div>

        <script>
        async function loadStats() {
            let r = await fetch('/stats');
            let s = await r.json();
            document.getElementById('stats').innerHTML = `
                <div class='box'>
                    <div>Total Chunks: <span class='big'>${s.total}</span></div>
                    <div>Completed: <span class='big'>${s.completed}</span></div>
                    <div>Leased: <span class='big'>${s.leased}</span></div>
                    <div>Pending: <span class='big'>${s.pending}</span></div>
                    <hr>
                    <div>Progress:</div>
                    <div class='big'>${s.progress}%</div>
                </div>
            `;
        }

        async function resetLeases() {
            if (!confirm('Reclaim leases older than 3 days?')) return;
            let r = await fetch('/admin/reset_leases', { method: 'POST' });
            let result = await r.json();
            alert('Reclaimed ' + result.reclaimed + ' leases.');
            loadStats();
        }

        loadStats();
        </script>       

    </body>
    </html>
    ";
    return Results.Content(html, "text/html");
});

app.Run();