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

#ifdef CONFIG_IDF_TARGET_ESP32C3
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "hal/adc_types.h"

static adc_oneshot_unit_handle_t adc1_handle = NULL;
static adc_cali_handle_t adc1_cali_handle = NULL;
static bool adc_initialized = false;

// Initialize ADC for VTarget measurement on GPIO2 (ADC1_CHANNEL_2)
static void vtarget_adc_init(void) {
    if (adc_initialized) {
        return;
    }
    
    // Configure ADC1
    adc_oneshot_unit_init_cfg_t init_config = {
        .unit_id = ADC_UNIT_1,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config, &adc1_handle));
    
    // Configure ADC1 Channel 2 (GPIO2)
    adc_oneshot_chan_cfg_t config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_11,  // 0-3.3V range
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, ADC_CHANNEL_2, &config));
    
    // Setup calibration
    adc_cali_curve_fitting_config_t cali_config = {
        .unit_id = ADC_UNIT_1,
        .atten = ADC_ATTEN_DB_11,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    esp_err_t ret = adc_cali_create_scheme_curve_fitting(&cali_config, &adc1_cali_handle);
    if (ret == ESP_OK) {
        adc_initialized = true;
    }
}

// Read VTarget voltage in millivolts (compensated for 1/2 voltage divider)
// Takes 20 samples and returns the average for better accuracy
static uint16_t vtarget_read_mv(void) {
    if (!adc_initialized) {
        vtarget_adc_init();
    }
    
    if (!adc1_handle) {
        return 0;
    }
    
    uint32_t voltage_sum = 0;
    uint8_t valid_samples = 0;
    
    // Read ADC 20 times and average
    for (int i = 0; i < 20; i++) {
        int adc_raw = 0;
        int voltage_mv = 0;
        
        // Read ADC
        esp_err_t ret = adc_oneshot_read(adc1_handle, ADC_CHANNEL_2, &adc_raw);
        if (ret != ESP_OK) {
            continue;
        }
        
        // Convert to voltage
        if (adc1_cali_handle) {
            ret = adc_cali_raw_to_voltage(adc1_cali_handle, adc_raw, &voltage_mv);
            if (ret != ESP_OK) {
                continue;
            }
        } else {
            // Fallback without calibration
            voltage_mv = adc_raw * 3300 / 4095;
        }
        
        voltage_sum += voltage_mv;
        valid_samples++;
    }
    
    if (valid_samples == 0) {
        return 0;
    }
    
    // Calculate average and compensate for 1/2 voltage divider (multiply by 2)
    uint16_t avg_voltage = (uint16_t)(voltage_sum / valid_samples);
    return avg_voltage * 2;
}
#endif // CONFIG_IDF_TARGET_ESP32C3

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
#ifdef CONFIG_IDF_TARGET_ESP32C3
      {
        uint16_t voltage_mv = vtarget_read_mv();
        *response++ = (uint8_t)(voltage_mv & 0xFF);        // Low byte
        *response++ = (uint8_t)((voltage_mv >> 8) & 0xFF); // High byte
        num += 2;  // 2 bytes in response
      }
#endif
      break;
    case ID_DAP_Vendor2:  break;
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
