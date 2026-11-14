#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>

void secret_backdoor(void) {
    FILE *f = fopen("/tmp/pwned.flag", "w");
    if (f) {
        fprintf(f, "PWNED by buffer overflow via /api/validate-ticker\n");
        fclose(f);
    }
    printf("[native] BACKDOOR REACHED - attacker controls RIP\n");
    fflush(stdout);
    _exit(0);
}

void validate_ticker(char *input) {
    char buf[64];
    strcpy(buf, input);
    printf("[native] ticker accepted: %s\n", buf);
}

int main(void) {
    char line[2048];
    ssize_t n = read(0, line, sizeof(line) - 1);
    if (n <= 0) {
        return 0;
    }
    line[n] = '\0';

    char *nl = strchr(line, '\n');
    if (nl) {
        *nl = '\0';
    }

    validate_ticker(line);
    return 0;
}
