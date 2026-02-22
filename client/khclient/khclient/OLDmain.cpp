#include <windows.h>
#include <iostream>
#include <thread>
#include <vector>
#include <string>
#include <sstream>
#include <regex>
#include <filesystem>
#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

// ================= CONFIG =================


//https://api.cocheat.com/chunkstats

//std::string SERVER = "http://localhost:8000"; // CHANGE THIS
std::string SERVER = "https://api.cocheat.com"; // CHANGE THIS
std::string WORKER_ID = "PC-" + std::to_string(GetCurrentProcessId());

// ================= UTIL ===================

namespace fs = std::filesystem;

void checkFoundFile()
{
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);

    fs::path exeDir = fs::path(exePath).parent_path();
    fs::path file = exeDir / "foundNEW.txt";

    if (fs::exists(file))
    {
        MessageBoxA(
            nullptr,
            "PRIVATE KEY FOUND!\n\nCheck foundNEW.txt",
            "KeyHunt",
            MB_OK | MB_ICONWARNING
        );

        std::cout << "[!] foundNEW.txt detected at: "
            << file << std::endl;

        exit(0);
    }
}




std::string getExecutableDir()
{
    char path[MAX_PATH];
    GetModuleFileNameA(nullptr, path, MAX_PATH);

    std::string full(path);
    size_t pos = full.find_last_of("\\/");
    return (pos == std::string::npos) ? "" : full.substr(0, pos);
}


std::string strip0x(const std::string& hex)
{
    if (hex.size() > 2 && hex[0] == '0' && (hex[1] == 'x' || hex[1] == 'X'))
        return hex.substr(2);
    return hex;
}

bool foundKeyInOutput(const std::string& line)
{
    static std::regex re(R"(\[F:\s*(\d+)\])");
    std::smatch match;
    if (std::regex_search(line, match, re)) {
        int f = std::stoi(match[1]);
        return f > 0;
    }
    return false;
}

// =============== CURL =====================

size_t writeCallback(char* ptr, size_t size, size_t nmemb, void* userdata)
{
    std::string* s = (std::string*)userdata;
    s->append(ptr, size * nmemb);
    return size * nmemb;
}

std::string httpPost(const std::string& url, const json& body)
{
    CURL* curl = curl_easy_init();
    std::string response;

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POST, 1L);

    std::string payload = body.dump();
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);


    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

    curl_easy_perform(curl);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    return response;
}

// ============== WORKER ====================

void runWorker()
{
    while (true)
    {
        std::string r = httpPost(SERVER + "/lease", {
            {"workerId", WORKER_ID},
            {"count", 1}
            });

        auto jobs = json::parse(r, nullptr, false);
        if (!jobs.is_array() || jobs.empty()) {
            std::cout << "[" << WORKER_ID << "] No jobs available, waiting...\n";
            Sleep(5000);
            continue;
        }

        auto job = jobs[0];
        int chunkId = job["chunkId"];
        std::string start = strip0x(job["start"]);
        std::string end = strip0x(job["end"]);


        std::stringstream cmd;
        cmd << "KeyHunt-Cuda.exe "
            << "-t 20480 "
            << "-g "
            << "--gpui 0 "
            << "--gpux 256,256 "
            << "-o foundNEW.txt "
            << "-m address "
            << "--coin BTC "
            << "--range " << start << ":" << end
            << " 1J555m5SFdE3AVvgTCP7GZgJBmndM8e9xQ";

       // std::stringstream cmd;
       // cmd << "KeyHunt-Cuda --range " << start << ":" << end;
        std::string command = cmd.str();

        // ---------- PIPE SETUP ----------
      /*  SECURITY_ATTRIBUTES sa{};
        sa.nLength = sizeof(sa);
        sa.bInheritHandle = TRUE;

        HANDLE hRead = NULL, hWrite = NULL;
        CreatePipe(&hRead, &hWrite, &sa, 0);
        SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0);
        */

        STARTUPINFOA si{};
        PROCESS_INFORMATION pi{};
        si.cb = sizeof(si);


        //si.dwFlags = STARTF_USESTDHANDLES;
        //si.hStdOutput = hWrite;
        //si.hStdError = hWrite;




        std::vector<char> cmdline(command.begin(), command.end());
        cmdline.push_back('\0');

        std::string workDir = getExecutableDir();

      /*  CreateProcessA(
            nullptr,
            cmdline.data(),
            nullptr, nullptr,
            TRUE,
            CREATE_NO_WINDOW,
            nullptr,
            workDir.c_str(),   // <<< CURRENT DIRECTORY SET HERE
            &si,
            &pi
        ); */


        BOOL ok = CreateProcessA(
            nullptr,
            cmdline.data(),
            nullptr, nullptr,
            FALSE,
            0,
            nullptr, 
            workDir.c_str(),   // <<< CURRENT DIRECTORY SET HERE
            &si, &pi
        );

        //CloseHandle(hWrite);

        if (!ok) {
            std::cerr << "Failed to launch KeyHunt-Cuda\n";
          //  CloseHandle(hRead);
            continue;
        }

        //std::cout << "[Worker " << WORKER_ID << "] Started KeyHunt-Cuda"
        //    << " | Chunk " << chunkId
        //    << " | Range " << start << ":" << end
        //    << std::endl;

        // ---------- READ OUTPUT ----------
        /*
        char buffer[4096];
        DWORD bytesRead;
        std::string lineBuffer;

        while (ReadFile(hRead, buffer, sizeof(buffer) - 1, &bytesRead, nullptr))
        {
            buffer[bytesRead] = '\0';
            lineBuffer += buffer;

            size_t pos;
            while ((pos = lineBuffer.find('\n')) != std::string::npos)
            {
                std::string line = lineBuffer.substr(0, pos);
                lineBuffer.erase(0, pos + 1);

//                std::cout << line << std::endl;
                std::cout << "[KeyHunt] " << line << std::endl;


                if (foundKeyInOutput(line))
                {
                    MessageBoxA(
                        nullptr,
                        "PRIVATE KEY FOUND!\nKeyHunt-Cuda reported [F > 0]",
                        "KEY FOUND",
                        MB_ICONINFORMATION | MB_OK
                    );

                    TerminateProcess(pi.hProcess, 0);
                    ExitProcess(0);
                }
            }
        }
        */



        // ---------- HEARTBEAT LOOP ----------
        while (WaitForSingleObject(pi.hProcess, 600000) == WAIT_TIMEOUT)
        {
            httpPost(SERVER + "/heartbeat", {
                {"workerId", WORKER_ID},
                {"chunkId", chunkId}
                });

            std::cout << "[Worker " << WORKER_ID << "] Still running chunk "
                << chunkId << "..." << std::endl;

        }

        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        //CloseHandle(hRead);


        httpPost(SERVER + "/complete", {
            {"workerId", WORKER_ID},
            {"chunkId", chunkId}
            });

       // auto file = std::filesystem::absolute("foundNEW.txt");

        /*
        if (std::filesystem::exists(std::filesystem::current_path() / "foundNEW.txt"))
        //if (std::filesystem::exists(file))
//        if (std::filesystem::exists("foundNEW.txt"))
        {
            MessageBoxA(
                nullptr,
                "PRIVATE KEY FOUND!\n\nCheck foundNEW.txt",
                "KeyHunt",
                MB_OK | MB_ICONWARNING
            );

            std::cout << "\n[!] foundNEW.txt detected. Exiting client.\n";
            exit(0);
        }
        */

        checkFoundFile();


    }
}

// ============== MAIN ======================

int main(int argc, char** argv)
{
    int workers = argc > 1 ? atoi(argv[1]) : 1;

    curl_global_init(CURL_GLOBAL_ALL);

    std::vector<std::thread> threads;
    for (int i = 0; i < workers; i++)
        threads.emplace_back(runWorker);

    for (auto& t : threads)
        t.join();

    return 0;
}