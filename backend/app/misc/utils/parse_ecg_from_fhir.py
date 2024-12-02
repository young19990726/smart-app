import json

import matplotlib.pyplot as plt
import numpy as np
import os
import sys

from matplotlib.gridspec import GridSpec
from scipy import interpolate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.middleware.exception import exception_message
from app.misc.utils.aiecg_api import ecg_ai_model

### Extract ECG information from FHIR format ###
def extract_ecg_data(fhir_data):
    try:
        leads_data = {}
        metadata = {
            "resourceType": fhir_data.get("resourceType", ""),
            "id": fhir_data.get("id", ""),
            "status": fhir_data.get("status", ""),
            "code": [c.get("code", "")  for c in fhir_data.get("code", {}).get('coding', [])],
            "subject": fhir_data.get("subject", {}).get("reference", ""),
            "effectiveDateTime": fhir_data.get("effectiveDateTime", ""),
            "performer": [p.get("reference", "") for p in fhir_data.get("performer", [])],
            "device": fhir_data.get("device", {}).get("display", "")
        }
        mdc_code_to_lead = {"131329": 'Lead I', "131330": 'Lead II', "131389": 'Lead III', "131390": 'Lead aVR', "131391": 'Lead aVL', "131392": 'Lead aVF', "131331": 'Lead V1', "131332": 'Lead V2', "131333": 'Lead V3', "131334": 'Lead V4', "131335": 'Lead V5', "131336": 'Lead V6'}
        
        if "component" not in fhir_data:
            raise KeyError("This FHIR data without component")

        for component in fhir_data["component"]:
            lead_name = None
            for coding in component.get("code", {}).get("coding", []):
                if coding.get("system") == "urn:oid:2.16.840.1.113883.6.24":
                    code = coding.get("code")
                    if code in mdc_code_to_lead:
                        lead_name = mdc_code_to_lead[code]
                        break
            if not lead_name:
                continue
                
            sampled_data = component.get("valueSampledData", {})
            if sampled_data:
                origin = float(int(sampled_data.get("origin", {}).get("value")))
                factor = float(int(sampled_data.get("factor")))
                interval = float(int(sampled_data.get("interval")))
                interval_unit = sampled_data.get("intervalUnit", "ms")
                lower_limit = float(int(sampled_data.get("lowerLimit")))
                upper_limit = float(int(sampled_data.get("upperLimit")))
                ecg_data = sampled_data.get("data", "")

                if not ecg_data:
                    print(f"Warning: {lead_name} without data")
                    continue

                try:
                    raw_values = [float(x) for x in ecg_data.split(' ') if x]
                    scaled_values = [(x - origin) * factor for x in raw_values]
                    leads_data[lead_name] = {
                        "data": scaled_values,
                        "metadata": {"factor": factor, "origin": origin, "interval": interval, "intervalUnit": interval_unit, "lowerLimit": lower_limit, "upperLimit": upper_limit}
                    }
                except ValueError:
                    print(f"Warning: {lead_name} contain invalid data")
                    continue

        if not leads_data:
            missing_leads = set(mdc_code_to_lead.values()) - set(leads_data.keys())
            if missing_leads:
                print(f"Warning: without: {missing_leads}")
        
        return leads_data, metadata
        
    except Exception as e:
        print(f"An error occurred while processing ECG data: {exception_message(e)}")
        return None, None

### Convert ECG data to matrix format ###
def convert_to_matrix(leads_data):
    try:
        if not leads_data:
            return None
        
        lead_order = {'Lead I': 0, 'Lead II': 1, 'Lead III': 2, 'Lead aVR': 3, 'Lead aVL': 4, 'Lead aVF': 5, 'Lead V1': 6, 'Lead V2': 7, 'Lead V3': 8, 'Lead V4': 9, 'Lead V5': 10, 'Lead V6': 11}

        lengths = [len(lead_info['data']) for lead_info in leads_data.values()]
        if len(set(lengths)) > 1:
            raise ValueError("All leads must have the same number of data points")

        time_points = lengths[0]
        ecg_matrix = np.zeros((time_points, 12))

        for lead_name, lead_info in leads_data.items():
            if lead_name in lead_order:
                col_index = lead_order[lead_name]
                ecg_matrix[:, col_index] = lead_info['data']

        return ecg_matrix

    except Exception as e:
        print(f"An error occurred while converting to matrix: {exception_message(e)}")
        return None

### Resample ECG matrix to the format required by the AI model ###
def resample_ecg_matrix(ecg_matrix, target_length=5000):

    original_length = ecg_matrix.shape[0]
    num_leads = ecg_matrix.shape[1]

    if original_length == 5000:
        return ecg_matrix

    x_original = np.linspace(0, 1, original_length)
    x_target = np.linspace(0, 1, target_length)

    resampled_matrix = np.zeros((target_length, num_leads))

    for lead in range(num_leads):
        lead_data = ecg_matrix[:, lead]
        f = interpolate.interp1d(x_original, lead_data, kind='cubic')
        resampled_matrix[:, lead] = f(x_target)
    
    return resampled_matrix

### Plot ECG waveform from the matrix ###
def plot_ecg_from_matrix(ecg_matrix, uid, sample_rate=500):

    if ecg_matrix.shape[1] != 12:
        raise ValueError(f"Expected 12 leads, got {ecg_matrix.shape[1]}")

    fig = plt.figure(figsize=(15, 10))
    gs = GridSpec(4, 1, height_ratios=[1, 1, 1, 1.2], hspace=0)

    major_grid_color = '#FFB6C1'
    minor_grid_color = '#FFC1C9'

    leads_layout = [
        [(0, 'I'), (3, 'aVR'), (6, 'V1'), (9, 'V4')],   
        [(1, 'II'), (4, 'aVL'), (7, 'V2'), (10, 'V5')],
        [(2, 'III'), (5, 'aVF'), (8, 'V3'), (11, 'V6')],
        [(1, 'II')]
    ]

    duration = len(ecg_matrix) / sample_rate       
    t = np.linspace(0, duration, len(ecg_matrix))  
    points_per_segment = int(2.5 * sample_rate)    
    
    for row, leads in enumerate(leads_layout):
        ax = fig.add_subplot(gs[row])
        if row == 3:  
            lead_idx = leads[0][0]
            ax.plot(t, ecg_matrix[:, lead_idx], 'k-', linewidth=0.8)
            ax.text(-0.05, 1, 'II', color='green', fontsize=14, fontweight='normal')
        else:
            for i, (lead_idx, lead_name) in enumerate(leads):                                          
                x_offset = i * 2.5                                                                 
                data = ecg_matrix[:points_per_segment, lead_idx]                                        
                t_segment = np.linspace(0, 2.5, len(data))
                ax.plot(t_segment + x_offset, data, 'k-', linewidth=0.8)                                
                ax.text(x_offset - 0.05, 1, lead_name, color='green', fontsize=14, fontweight='normal') 

        ax.grid(True, which='major', color=major_grid_color, linestyle='-', alpha=0.8)  
        ax.grid(True, which='minor', color=minor_grid_color, linestyle='-', alpha=0.5)

        minor_ticks = np.arange(-2, 12, 0.04)  
        major_ticks = np.arange(-2, 12, 0.2)
        ax.set_xticks(major_ticks)
        ax.set_xticks(minor_ticks, minor=True)
        ax.set_yticks(major_ticks)
        ax.set_yticks(minor_ticks, minor=True)

        if row == 3: 
            ax.set_xlim(-1, 10)  
        else:
            ax.set_xlim(-1, 10)  
        ax.set_ylim(-1.5, 1.5)
        
        ax.set_xticklabels([])  
        ax.set_yticklabels([])

        for spine in ax.spines.values():  
            spine.set_visible(False)

        ax.tick_params(axis='both', which='both', length=0)  

    cal_ax = plt.axes([0.95, 0.1, 0.02, 0.1])  
    cal_ax.set_xticks([])
    cal_ax.set_yticks([])
    cal_ax.set_xlim(-0.5, 0.5)
    cal_ax.set_ylim(0, 1)
    for spine in cal_ax.spines.values():
        spine.set_visible(False)

    plt.subplots_adjust(right=0.95, left=0.05)  

    if uid:  
        
        plot_path = f"C:/Users/young/Desktop/DMC/smart-app/backend/file/image/{uid}.png"
        # plot_path = f"/home/young19990726/Project/smart-app/backend/file/image/{uid}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print('Image already saved')
    
    return plot_path
    # return fig

if __name__ == "__main__":

    '''
    <FHIR ECG code list>: https://build.fhir.org/ig/HL7/uv-pocd/ValueSet-11073MDC-metric.html

    <FHIR ECG example data>: https://build.fhir.org/observation-example-sample-data.json.html
    '''

    with open('/home/young19990726/Project/smart-app/backend/app/misc/utils/file/test.json', 'r') as f:
        fhir_data = json.load(f)
    
    leads_data, metadata = extract_ecg_data(fhir_data)
    uid = metadata.get('subject')[9:16]

    ecg_matrix = convert_to_matrix(leads_data)
    resampled_matrix = resample_ecg_matrix(ecg_matrix)
    matrix_data = resampled_matrix.T
    result = ecg_ai_model(matrix_data)
    print(result)
    fig = plot_ecg_from_matrix(resampled_matrix, sample_rate=500, uid=uid)
    plt.close()