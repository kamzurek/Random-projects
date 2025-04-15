#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <cmath>
#include <Windows.h>
#include <Psapi.h>

using namespace std;


bool is_prime(unsigned long long num) {
    if (num <= 1) return false;
    if (num == 2 || num == 3) return true;
    if (num % 2 == 0 || num % 3 == 0) return false;

    for (unsigned long long i = 5; i * i <= num; i += 6) {
        if (num % i == 0 || num % (i + 2) == 0) return false;
    }
    return true;
}

void cpu_stress() {
    while (true) {
        double result = 0;
        for (long i = 0; i < 100000000; ++i) {
            result += sqrt(i);
        }
    }
}

void cpu_stress2() {
    unsigned long long num = 2;
    while (true) {
        if (is_prime(num)) {}
        num++;
    }
}

void print_memory_usage() {
    PROCESS_MEMORY_COUNTERS pmc;
    if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
        cout << "Pamięć wirtualna (VmSize): " << pmc.PagefileUsage / (1024 * 1024) << " MB" << endl;
        cout << "Pamięć fizyczna (VmRSS): " << pmc.WorkingSetSize / (1024 * 1024) << " MB" << endl;
    }
    else {
        cerr << "Nie udało się uzyskać danych o pamięci!" << endl;
    }
}

void print_cpu_usage() {
    FILETIME idleTime1, kernelTime1, userTime1;
    FILETIME idleTime2, kernelTime2, userTime2;
    GetSystemTimes(&idleTime1, &kernelTime1, &userTime1);
    Sleep(1000);
    GetSystemTimes(&idleTime2, &kernelTime2, &userTime2);

    ULARGE_INTEGER idle1, kernel1, user1;
    ULARGE_INTEGER idle2, kernel2, user2;

    idle1.LowPart = idleTime1.dwLowDateTime;
    idle1.HighPart = idleTime1.dwHighDateTime;
    kernel1.LowPart = kernelTime1.dwLowDateTime;
    kernel1.HighPart = kernelTime1.dwHighDateTime;
    user1.LowPart = userTime1.dwLowDateTime;
    user1.HighPart = userTime1.dwHighDateTime;

    idle2.LowPart = idleTime2.dwLowDateTime;
    idle2.HighPart = idleTime2.dwHighDateTime;
    kernel2.LowPart = kernelTime2.dwLowDateTime;
    kernel2.HighPart = kernelTime2.dwHighDateTime;
    user2.LowPart = userTime2.dwLowDateTime;
    user2.HighPart = userTime2.dwHighDateTime;

    ULONGLONG systemTime1 = kernel1.QuadPart + user1.QuadPart;
    ULONGLONG systemTime2 = kernel2.QuadPart + user2.QuadPart;
    ULONGLONG idleTime1Value = idle1.QuadPart;
    ULONGLONG idleTime2Value = idle2.QuadPart;

    ULONGLONG systemTimeDelta = systemTime2 - systemTime1;
    ULONGLONG idleTimeDelta = idleTime2Value - idleTime1Value;

    double cpuUsage = 100.0 - (double)(idleTimeDelta) / (double)(systemTimeDelta) * 100.0;

    cout << "Obciążenie CPU: " << cpuUsage << "%" << endl;
}



int main() {
    setlocale(LC_ALL, "");

    const size_t GB = 1024ULL * 1024ULL * 1024ULL;
    const size_t SIZE = 22ULL * GB; //Zmień tą liczbę (*22*) i dostosuj do swojego hardware np. dla 16GB RAM ustaw 12ULL aby nie dostać BlueScreena
    cout << "Rezerwuję ok. 22 GB pamięci..." << endl;

    char* big_array = new(nothrow) char[SIZE];
    if (!big_array) {
        cerr << "Nie udało się zaalokować pamięci!" << endl;
        return 1;
    }

    memset(big_array, 1, SIZE);
    unsigned int num_threads = thread::hardware_concurrency();
    vector<thread> threads;

    for (unsigned int i = 0; i < num_threads; ++i) {
        threads.push_back(thread(cpu_stress));
    }

    for (unsigned int i = 0; i < num_threads; ++i) {
        threads.push_back(thread(cpu_stress2));
    }

    cout << "\nCzekam 10 sekund na obciążenie..." << endl;
    Sleep(10000);

    cout << "Pamięć została przydzielona i wypełniona." << endl;

    cout << "\n=== Statystyki pamięci procesu ===" << endl;
    print_memory_usage();

    cout << "\n=== Statystyki procesora ===" << endl;
    print_cpu_usage();

    cout << "Naciśnij Enter, aby zakończyć..." << endl;
    cin.get();

    delete[] big_array;
    for (auto& t : threads) {
        t.detach();
    }
    return 0;
}
