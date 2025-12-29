/*
 * Copyright (c) 2013-2017 ARM Limited. All rights reserved.
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the License); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * ----------------------------------------------------------------------
 *
 * $Date:        1. December 2017
 * $Revision:    V2.0.0
 *
 * Project:      CMSIS-DAP Source
 * Title:        DAP_vendor.c CMSIS-DAP Vendor Commands
 *
 *---------------------------------------------------------------------------*/

#include "components/DAP/config/DAP_config.h"
#include "components/DAP/include/DAP.h"
#include "components/elaphureLink/elaphureLink_protocol.h"
#include <stdbool.h>
#include <stdlib.h>

// VTarget sensing is only available on ESP32-C3/ESP32-S3 XIAO boards
#if defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
#include "driver/adc.h"
#include "esp_adc_cal.h"
#include "esp_log.h"
#include "main/vtarget_pwm.h"

static const char *TAG = "DAP_vendor";
static esp_adc_cal_characteristics_t *adc_chars = NULL;
static bool adc_initialized = false;

// Cleanup ADC resources
__attribute__((unused))
static void vtarget_adc_deinit(void) {
    if (adc_chars) {
        free(adc_chars);
        adc_chars = NULL;
    }
    adc_initialized = false;
}

// Initialize ADC for VTarget measurement on GPIO2 (ADC1_CHANNEL_2)
static void vtarget_adc_init(void) {
    if (adc_initialized) {
        return;
    }
    
    // Configure ADC1 width (12-bit resolution)
    adc1_config_width(ADC_WIDTH_BIT_12);
    
    // Configure ADC1 Channel 2 (GPIO2) with 11dB attenuation (0-3.3V range)
    adc1_config_channel_atten(ADC1_CHANNEL_2, ADC_ATTEN_DB_11);
    
    // Characterize ADC for calibration
    adc_chars = calloc(1, sizeof(esp_adc_cal_characteristics_t));
    if (!adc_chars) {
        ESP_LOGE(TAG, "Failed to allocate ADC calibration memory");
        return;
    }
    
    esp_adc_cal_value_t val_type = esp_adc_cal_characterize(ADC_UNIT_1, ADC_ATTEN_DB_11, ADC_WIDTH_BIT_12, 1100, adc_chars);
    
    adc_initialized = true;
    ESP_LOGI(TAG, "VTarget ADC initialized on GPIO2 (ADC1_CH2), calibration type: %d", val_type);
}

// Read VTarget voltage in millivolts (compensated for 1/2 voltage divider)
// Takes 20 samples and returns the average for better accuracy
// Returns 0xFFFF on error
static uint16_t vtarget_read_mv(void) {
    if (!adc_initialized) {
        vtarget_adc_init();
    }
    
    if (!adc_chars) {
        ESP_LOGE(TAG, "ADC not initialized or calibration failed");
        return 0xFFFF;  // Error indicator
    }
    
    uint32_t voltage_sum = 0;
    uint8_t valid_samples = 0;
    
    // Read ADC 20 times and average
    for (int i = 0; i < 20; i++) {
        int adc_raw = adc1_get_raw(ADC1_CHANNEL_2);
        
        if (adc_raw < 0) {
            continue;
        }
        
        // Convert to voltage using calibration
        uint32_t voltage_mv = esp_adc_cal_raw_to_voltage(adc_raw, adc_chars);
        
        voltage_sum += voltage_mv;
        valid_samples++;
    }
    
    if (valid_samples == 0) {
        ESP_LOGW(TAG, "No valid ADC samples obtained");
        return 0xFFFF;  // Error indicator
    }
    
    // Calculate average and compensate for 1/2 voltage divider (multiply by 2)
    uint16_t avg_voltage = (uint16_t)(voltage_sum / valid_samples);
    uint16_t result = avg_voltage * 2;
    
    ESP_LOGD(TAG, "VTarget read: %d mV (raw avg: %d mV, samples: %d)", result, avg_voltage, valid_samples);
    return result;
}

#else
// Provide weak stub for platforms without VTarget support
__attribute__((weak)) esp_err_t vtarget_set_voltage(uint16_t voltage_mv) {
    (void)voltage_mv;
    return ESP_ERR_NOT_SUPPORTED;
}
#endif // ESP32/ESP32-C3/ESP32-S3

//**************************************************************************************************
/**
\defgroup DAP_Vendor_Adapt_gr Adapt Vendor Commands
\ingroup DAP_Vendor_gr
@{

The file DAP_vendor.c provides template source code for extension of a Debug Unit with
Vendor Commands. Copy this file to the project folder of the Debug Unit and add the
file to the MDK-ARM project under the file group Configuration.
*/

/** Process DAP Vendor Command and prepare Response Data
\param request   pointer to request data
\param response  pointer to response data
\return          number of bytes in response (lower 16 bits)
                 number of bytes in request (upper 16 bits)
*/
uint32_t DAP_ProcessVendorCommand(const uint8_t *request, uint8_t *response) {
  uint32_t num = (1U << 16) | 1U;

  *response++ = *request;        // copy Command ID

  switch (*request++) {          // first byte in request is Command ID
    case ID_DAP_Vendor0:
#if 0                            // example user command
      num += 1U << 16;           // increment request count
      if (*request == 1U) {      // when first command data byte is 1
        *response++ = 'X';       // send 'X' as response
        num++;                   // increment response count
      }
#endif
      break;

    case ID_DAP_Vendor1:  // Read VTarget voltage
#if defined(CONFIG_IDF_TARGET_ESP32) || defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
      {
        uint16_t voltage_mv = vtarget_read_mv();
        *response++ = (uint8_t)(voltage_mv & 0xFF);        // Low byte
        *response++ = (uint8_t)((voltage_mv >> 8) & 0xFF); // High byte
        num += 2;  // 2 bytes in response
        // Note: 0xFFFF (65535) indicates read error
      }
#else
      // VTarget sensing not supported on this target
      *response++ = 0xFF;  // Return 0xFFFF to indicate not supported
      *response++ = 0xFF;
      num += 2;
#endif
      break;

    case ID_DAP_Vendor2:  // Set VTarget voltage (1250-5000 mV)
#if defined(CONFIG_IDF_TARGET_ESP32) || defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32S3)
      {
        num += 2U << 16;  // 2 bytes in request (voltage low, high)
        uint8_t voltage_low = *request++;
        uint8_t voltage_high = *request++;
        uint16_t voltage_mv = (uint16_t)voltage_low | ((uint16_t)voltage_high << 8);
        
        ESP_LOGI(TAG, "Set VTarget request: %d mV", voltage_mv);
        esp_err_t ret = vtarget_set_voltage(voltage_mv);
        
        if (ret == ESP_OK) {
          *response++ = 0x00;  // Success
          ESP_LOGI(TAG, "VTarget set successfully to %d mV", voltage_mv);
        } else if (ret == ESP_ERR_INVALID_ARG) {
          *response++ = 0x01;  // Invalid voltage range (not 1250-5000 mV)
          ESP_LOGW(TAG, "Invalid voltage range: %d mV (valid: 1250-5000 mV)", voltage_mv);
        } else {
          *response++ = 0xFF;  // Other error
          ESP_LOGE(TAG, "Failed to set VTarget: %s", esp_err_to_name(ret));
        }
        num += 1;  // 1 byte status response
      }
#else
      // VTarget control not supported on this target
      num += 2U << 16;  // Still consume 2 bytes from request
      request += 2;
      *response++ = 0xFF;  // Not supported error
      num += 1;
#endif
      break;
    case ID_DAP_Vendor3:  break;
    case ID_DAP_Vendor4:  break;
    case ID_DAP_Vendor5:  break;
    case ID_DAP_Vendor6:  break;
    case ID_DAP_Vendor7:  break;
    case ID_DAP_Vendor8:
      num = el_vendor_command(request, response);
      break;
    case ID_DAP_Vendor9:  break;
    case ID_DAP_Vendor10: break;
    case ID_DAP_Vendor11: break;
    case ID_DAP_Vendor12: break;
    case ID_DAP_Vendor13: break;
    case ID_DAP_Vendor14: break;
    case ID_DAP_Vendor15: break;
    case ID_DAP_Vendor16: break;
    case ID_DAP_Vendor17: break;
    case ID_DAP_Vendor18: break;
    case ID_DAP_Vendor19: break;
    case ID_DAP_Vendor20: break;
    case ID_DAP_Vendor21: break;
    case ID_DAP_Vendor22: break;
    case ID_DAP_Vendor23: break;
    case ID_DAP_Vendor24: break;
    case ID_DAP_Vendor25: break;
    case ID_DAP_Vendor26: break;
    case ID_DAP_Vendor27: break;
    case ID_DAP_Vendor28: break;
    case ID_DAP_Vendor29: break;
    case ID_DAP_Vendor30: break;
    case ID_DAP_Vendor31: break;
  }

  return (num);
}

///@}
