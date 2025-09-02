NVCC = nvcc
CXX = g++

CUDA_ARCH = sm_60

# Directories
CUDA_PATH = /usr/local/cuda
SFML_PATH = /usr/local

# Compiler flags
NVCC_FLAGS = -arch=$(CUDA_ARCH) -O3 -std=c++14
CXX_FLAGS = -O3 -std=c++14 -fopenmp -pthread

# Include paths
INCLUDES = -I$(CUDA_PATH)/include -I$(SFML_PATH)/include

# Library paths and libraries
LIBS = -L$(CUDA_PATH)/lib64 -L$(SFML_PATH)/lib \
       -lcudart -lsfml-graphics -lsfml-window -lsfml-system

# Source files
CUDA_SRC = main-cuda.cu
CPP_SRC = 
TARGET = main-cuda

cuda: $(TARGET)

parallel:
	g++ -o main-parallel main-parallel.cpp -lsfml-graphics -lsfml-window -lsfml-system 

serial:
	g++ -o main-serial main-serial.cpp

$(TARGET): $(CUDA_SRC)
	$(NVCC) $(NVCC_FLAGS) $(INCLUDES) -o $(TARGET) $(CUDA_SRC) $(LIBS)

clean:
	rm -f $(TARGET) mandelbrot_cpu *.o

install_deps:
	sudo apt update
	sudo apt install -y libsfml-dev nvidia-cuda-toolkit

install_deps_arch:
	sudo pacman -S sfml cuda

check_cuda:
	nvcc --version
	nvidia-smi

.PHONY: all cpu_only clean install_deps install_deps_arch check_cuda help