// for LINUX!!

#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <unistd.h>
#include <sys/wait.h>
#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

static const std::string SERVER = "https://api.cocheat.com";
//static const std::string SERVER = "http://localhost:8000"; // CHANGE THIS

static const std::string WORKER_ID = "linux-worker-1";


// ---------------- CURL HELPERS ----------------

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

/*json httpPost(const std::string& url, const json& body) {
    CURL* curl = curl_easy_init();
    std::string response;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.dump().c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

    // Optional: ignore SSL issues if using self-signed certs
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    curl_easy_perform(curl);
    curl_easy_cleanup(curl);

    if (response.empty())
        return json();

    //return json::parse(response);

	std::cout << "SERVER RESPONSE:\n" << response << "\n";

	try {
		return json::parse(response);
	} catch (...) {
		std::cerr << "JSON parse failed!\n";
		return json();
	}



}
*/



json httpPost(const std::string& url, const json& body) {
    CURL* curl = curl_easy_init();
    std::string response;

    if (!curl)
        return json();

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    std::string bodyStr = body.dump();

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, bodyStr.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, bodyStr.size());

    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);

    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);

    // optional (for testing only)
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    CURLcode res = curl_easy_perform(curl);

    if (res != CURLE_OK) {
        std::cerr << "CURL Error: " << curl_easy_strerror(res) << "\n";
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    std::cout << "SERVER RESPONSE:\n" << response << "\n";

    try {
        return json::parse(response);
    } catch (...) {
        std::cerr << "JSON parse failed\n";
        return json();
    }
}




// ---------------- FILE CHECK ----------------

bool foundFileDetected() {
    std::filesystem::path p = std::filesystem::current_path() / "foundNEW.txt";
    return std::filesystem::exists(p);
}


// ---------------- MAIN WORK LOOP ----------------

int main() {
    curl_global_init(CURL_GLOBAL_ALL);

    while (true) {

        // Ask server for work
        json leaseReq = {
            {"workerId", WORKER_ID},
            {"count", 1}
        };

        json leaseResp = httpPost(SERVER + "/lease", leaseReq);

        if (!leaseResp.is_array() || leaseResp.empty()) {
            std::cout << "No jobs available, waiting...\n";
            std::this_thread::sleep_for(std::chrono::seconds(20));
            continue;
        }

        auto chunk = leaseResp[0];

        int chunkId = chunk["chunkId"];
        std::string start = chunk["start"];
        std::string end = chunk["end"];

        std::cout << "Leased chunk " << chunkId << "\n";

        // Launch KeyHunt-Cuda
        pid_t pid = fork();

        if (pid == 0) {
            // Child process
            execl("./KeyHunt",
                "./KeyHunt",
                "-r",
                (start + ":" + end).c_str(),
                (char*)NULL);

            std::cerr << "Failed to start KeyHunt-Cuda\n";
            exit(1);
        }

        // Parent: heartbeat loop
        while (true) {

            // Check if process finished
            int status;
            pid_t result = waitpid(pid, &status, WNOHANG);

            if (result == pid)
                break;

            // Send heartbeat
            httpPost(SERVER + "/heartbeat", {
                {"workerId", WORKER_ID},
                {"chunkId", chunkId}
                });

            std::cout << "[Heartbeat] chunk " << chunkId << "\n";

         
            std::this_thread::sleep_for(std::chrono::minutes(5));
        }

        // Mark complete
        httpPost(SERVER + "/complete", {
            {"workerId", WORKER_ID},
            {"chunkId", chunkId}
            });
        std::cout << "Completed chunk " << chunkId << "\n";

        // Check found file
        if (foundFileDetected()) {
            std::cout << "\n!!! PRIVATE KEY FOUND !!!\n";
            std::cout << "Check foundNEW.txt\n";
            kill(pid, SIGTERM);
            exit(0);
        }


    }

    curl_global_cleanup();
    return 0;
}
