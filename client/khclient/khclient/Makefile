CXX = g++-12
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra
LIBS = -lcurl -lpthread

TARGET = khclientimproved
SRC = khclientimproved.cpp

all:
	$(CXX) $(CXXFLAGS) $(SRC) -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET)
