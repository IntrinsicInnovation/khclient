#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <future>
#include <cstdlib>
#include <curl/curl.h>
#include "json.hpp"
#include <filesystem>
#include <fstream>
#include <sstream>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <limits.h>
#endif

using json = nlohmann::json;
namespace fs = std::filesystem;

//static const std::string SERVER = "https://khserverwindows-dsh7ebhkhpb4apbq.canadacentral-01.azurewebsites.net";
//static const std::string SERVER = "https://api.cocheat.com";
static const std::string SERVER = "https://localhost:5001";
//static const std::string SERVER = "https://khserver-gvfhb2h5ancpash9.canadacentral-01.azurewebsites.net";
//static const std::string SERVER = "https://khserver2-gjbcesdabwb9hufr.canadacentral-01.azurewebsites.net";

static const std::string WORKER_ID = "integrated-client";


// ---------------- HTTP ----------------

static size_t WriteCallback(void* contents,
    size_t size,
    size_t nmemb,
    void* userp)
{
    ((std::string*)userp)->append(
        (char*)contents,
        size * nmemb);

    return size * nmemb;
}


json httpPost(const std::string& url, const json& body)
{
    CURL* curl = curl_easy_init();
    std::string response;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(
        headers,
        "Content-Type: application/json");

    std::string payload = body.dump();

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, payload.size());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_SSLVERSION, CURL_SSLVERSION_TLSv1_2);

    CURLcode res = curl_easy_perform(curl);

    if (res != CURLE_OK)
    {
        std::cout << "CURL ERROR: "
            << curl_easy_strerror(res)
            << "\n";
    }

    long http_code = 0;
    curl_easy_getinfo(curl,
        CURLINFO_RESPONSE_CODE,
        &http_code);

    std::cout << "HTTP CODE: "
        << http_code << "\n";

    std::cout << "SERVER RAW:\n"
        << response << "\n";

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (response.empty())
        return json();

    try
    {
        return json::parse(response);
    }
    catch (...)
    {
        std::cerr << "JSON parse error\n";
        return json();
    }
}


// ---------------- REPORT FOUND ----------------

void reportFound(const std::string& key)
{
    httpPost(SERVER + "/report_found",
        {
            {"workerId", WORKER_ID},
            {"privateKey", key}
        });
}



fs::path getExecutableFolder() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    fs::path exePath(path);
    return exePath.parent_path(); // folder containing khclientwindows.exe
}


// ---------------- EXECUTABLE PATH ----------------

std::string getExecutableDir()
{

#ifdef _WIN32

    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    return fs::path(path).parent_path().string();

#else

    char exePath[PATH_MAX];

    ssize_t len = readlink(
        "/proc/self/exe",
        exePath,
        sizeof(exePath) - 1);

    if (len == -1)
        return "";

    exePath[len] = '\0';

    return fs::path(exePath).parent_path().string();

#endif
}


// ---------------- CHECK FOUND FILE ----------------

void checkFoundFile()
{
    fs::path exeDir = getExecutableDir();
    fs::path file = exeDir / "foundNEW.txt";

    if (!fs::exists(file))
        return;

    std::cerr << "\n[!] PRIVATE KEY FOUND!\n";
    std::cerr << "[!] Reading foundNEW.txt...\n";

    std::ifstream in(file);
    std::stringstream buffer;

    buffer << in.rdbuf();

    std::string key = buffer.str();

    key.erase(key.find_last_not_of(" \n\r\t") + 1);

    std::cerr << "[!] Key: "
        << key << std::endl;

    reportFound(key);

    fs::remove(file);

    std::cerr << "[!] Reported to server\n";

    exit(0);
}


// ---------------- LEASE ----------------

json leaseChunk()
{
    return httpPost(
        SERVER + "/lease",
        {
            {"workerId", WORKER_ID},
            {"count", 1}
        });
}


// ---------------- MAIN ----------------

int main()
{
    curl_global_init(CURL_GLOBAL_ALL);

    std::cout << "Integrated client started\n";

    auto futureLease =
        std::async(
            std::launch::async,
            leaseChunk);

    while (true)
    {
        json leaseResp = futureLease.get();

        if (!leaseResp.is_array() ||
            leaseResp.empty())
        {
            std::cout << "No jobs, retrying...\n";

            std::this_thread::sleep_for(
                std::chrono::seconds(2));

            futureLease =
                std::async(
                    std::launch::async,
                    leaseChunk);

            continue;
        }

        auto chunk = leaseResp[0];

        int chunkId = chunk["chunkId"];
        std::string start = chunk["start"];
        std::string end = chunk["end"];

        if (start.rfind("0x", 0) == 0)
            start = start.substr(2);

        if (end.rfind("0x", 0) == 0)
            end = end.substr(2);

        std::cout << "\nLeased chunk "
            << chunkId
            << " | "
            << start
            << " → "
            << end
            << "\n";

        futureLease =
            std::async(
                std::launch::async,
                leaseChunk);

        std::cout << "Launching keyhunt\n";

        fs::path keyhuntPath;

#ifdef _WIN32
        //std::string keyhunt = "KeyHunt.exe ";
        fs::path exeDir = getExecutableFolder();
        keyhuntPath = exeDir / "KeyHunt.exe"; // full path to KeyHunt.exe

#else
        std::string keyhunt = "./KeyHunt ";

        // Linux: KeyHunt in the same folder as the client
        //fs::path exeDir = getExecutableFolder(); // reuse same helper, or just current dir
        keyhuntPath = "./KeyHunt"; // Linux binary has no .exe



#endif

        std::string cmd =
            //keyhunt +
            "\"" + keyhuntPath.string() + "\" "
            "-g --gpui 0 "
            "--gpux 256,256 "
            "-o foundNEW.txt "
            "-m address --coin BTC "
            "--range " + start + ":" + end +
            " 1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU";

        //Test ramge (shoudl be very fast to test):
        //"--range dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e148f00000000:dbdd1b55c9e880d5b66ea8b3e8bfe8ef03a41aa9326470b8661e148fffffffff"
        //    " 1J555m5SFdE3AVvgTCP7GZgJBmndM8e9xQ";

        int ret = system(cmd.c_str());

        std::cout << "KeyHunt finished!! -- ("
            << ret
            << ")\n";

        httpPost(
            SERVER + "/complete",
            {
                {"workerId", WORKER_ID},
                {"chunkId", chunkId}
            });

        checkFoundFile();
    }

    curl_global_cleanup();
    return 0;
}