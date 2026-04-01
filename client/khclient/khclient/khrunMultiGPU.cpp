#include <iostream>
#include <string>
#include <cuda_runtime.h>

int getGpuId(int argc, char* argv[])
{
    int gpu_id = 0;

    for (int i = 1; i < argc; i++)
    {
        std::string arg = argv[i];

        if (arg == "-gpu" && i + 1 < argc)
        {
            gpu_id = std::stoi(argv[i + 1]);
            i++;
        }
    }

    return gpu_id;
}

int main(int argc, char* argv[])
{
    int gpu_id = getGpuId(argc, argv);

    cudaError_t err = cudaSetDevice(gpu_id);
    if (err != cudaSuccess)
    {
        std::cerr << "CUDA error: "
                  << cudaGetErrorString(err) << std::endl;
        return 1;
    }

    std::cout << "Running on GPU " << gpu_id << std::endl;

    // Your CUDA code here

    return 0;
}