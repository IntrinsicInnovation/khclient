#include <windows.h>
#include <iostream>
#include <thread>
#include <vector>
#include <string>
#include <sstream>
#include <curl/curl.h>
#include "json.hpp"

using json = nlohmann::json;

std::string SERVER = "http://SERVER_IP:8000"; // change SERVER_IP
std::string WORKER_ID = "PC-" + std::to_string(GetCurrentProcessId());

std::string httpPost(std::string url, json body)
{
    CURL* curl = curl_easy_init();
    std::string response;

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.dump().c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION,
        +[](char* ptr, size_t s, size_t n, void* d) {
            ((std::string*)d)->append(ptr, s * n);
            return s * n;
        });
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    return response;
}

void runWorker()
{
    while (true)
    {
        auto r = httpPost(SERVER + "/lease", {
            {"workerId", WORKER_ID},
            {"count", 1}
        });

        auto jobs = json::parse(r);
        if (jobs.empty()) return;

        auto job = jobs[0];
        int chunkId = job["chunkId"];
        std::string start = job["start"];
        std::string end = job["end"];

        std::stringstream cmd;
        cmd << "KeyHunt-Cuda "
            << "--range " << start << ":" << end;

        STARTUPINFOA si{};
        PROCESS_INFORMATION pi{};
        si.cb = sizeof(si);
        std::string command = cmd.str();

        CreateProcessA(nullptr, command.data(),
            nullptr, nullptr, FALSE, 0,
            nullptr, nullptr, &si, &pi);

        while (WaitForSingleObject(pi.hProcess, 600000) == WAIT_TIMEOUT)
        {
            httpPost(SERVER + "/heartbeat", {
                {"workerId", WORKER_ID},
                {"chunkId", chunkId}
            });
        }

        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);

        httpPost(SERVER + "/complete", {
            {"workerId", WORKER_ID},
            {"chunkId", chunkId}
        });
    }
}

int main(int argc, char** argv)
{
    int workers = argc > 1 ? atoi(argv[1]) : 1;
    curl_global_init(CURL_GLOBAL_ALL);

    std::vector<std::thread> threads;
    for (int i = 0; i < workers; i++)
        threads.emplace_back(runWorker);

    for (auto& t : threads) t.join();
}
