# Multi-target firmware builder for wireless-esp8266-dap
# Based on EvgeniyBlinov's docker branch, adapted for ESP-IDF targets and ESP32-C3 XIAO.
#
# Usage:
#   docker build --build-arg TARGET=esp32c3 -t wireless-dap .
#   docker run --rm -v $(pwd)/dist:/builder/dist wireless-dap
#
# Supported TARGET values: esp32c3 (default), esp32s3, esp32, esp8266

FROM espressif/idf:v5.3.2

SHELL ["/bin/bash", "-c"]

ARG TARGET=esp32c3

ENV IDF_TARGET=${TARGET}

WORKDIR /builder

# Copy project (wifi_configuration.h is excluded via .dockerignore)
COPY . .

RUN set -ex && \
    idf.py -DIDF_TARGET=${TARGET} build

# Merge bootloader + partition table + app into a single flashable binary.
# ESP8266 bootloader sits at 0x0; all ESP32 variants sit at 0x1000.
RUN set -ex && \
    mkdir -p dist && \
    if [ "${TARGET}" = "esp8266" ]; then \
        bootloader_addr=0x0; \
    else \
        bootloader_addr=0x1000; \
    fi && \
    esptool.py \
        --chip ${TARGET} \
        merge_bin \
        -o dist/wireless_dap_full_${TARGET}.bin \
        ${bootloader_addr} build/bootloader/bootloader.bin \
        0x8000 build/partition_table/partition-table.bin \
        0x10000 build/wireless_esp_dap.bin

EXPOSE 8000

# Serve the merged binary so it can be downloaded from http://<container>:8000/dist/
CMD ["python3", "-m", "http.server", "8000", "--directory", "/builder"]
