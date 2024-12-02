import array
import base64 
import numpy as np
import os
import SPxml
import sys
import traceback
import xml.etree.ElementTree as ET
import xmltodict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.middleware.exception import exception_message
from app.misc.utils.aiecg_api import ecg_ai_model
from app.misc.utils.parse_ecg_from_fhir import resample_ecg_matrix


### Parse ECG xml file ###
## ge ##
def parse_ge_xml(xml_path):
    try:
        with open(xml_path, "rb") as f:
            ecg = xmltodict.parse(f.read().decode("utf8"))
    except Exception as e:
        raise ValueError(f"Error loading ge xml file: {exception_message(e)}")

    if "RestingECG" not in ecg or "Waveform" not in ecg["RestingECG"]:
        raise ValueError("This ge xml file had invalid structure.")

    leads = {id: {"data": np.array([]), "info": {}} for id in ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]}

    patient_data = ecg["RestingECG"].get("PatientDemographics", {})  # extract patient information
    patient_id = patient_data.get("PatientID", "Unknown")
    age = patient_data.get("PatientAge", "Unknown")
    gender = patient_data.get("Gender", "Unknown")

    for waveform in ecg["RestingECG"]["Waveform"]:  # extract waveform information
        if waveform.get("WaveformType") == "Rhythm":
            sample_base = waveform.get("SampleBase", "")
            high_pass_filter = waveform.get("HighPassFilter", "")
            low_pass_filter = waveform.get("LowPassFilter", "")

            for lead_index in waveform.get("LeadData", []):  # parse lead data
                try:
                    lead_id = lead_index["LeadID"]
                    lead_b64 = base64.b64decode(lead_index["WaveFormData"])
                    lead_vals = np.array(array.array("h", lead_b64))
                    leads[lead_id]["data"] = lead_vals  # store waveform data and additional metadata for each lead
                    leads[lead_id]["info"] = {
                        "LeadByteCountTotal": int(lead_index["LeadByteCountTotal"]),
                        "LeadTimeOffset": int(lead_index["LeadTimeOffset"]),
                        "LeadSampleCountTotal": int(lead_index["LeadSampleCountTotal"]),
                        "LeadAmplitudeUnitsPerBit": float(lead_index["LeadAmplitudeUnitsPerBit"]),
                        "LeadAmplitudeUnits": lead_index["LeadAmplitudeUnits"],
                        "LeadHighLimit": int(lead_index["LeadHighLimit"]),
                        "LeadLowLimit": int(lead_index["LeadLowLimit"]),
                        "LeadOffsetFirstSample": int(lead_index["LeadOffsetFirstSample"]),
                        "FirstSampleBaseline": int(lead_index["FirstSampleBaseline"]),
                        "LeadSampleSize": int(lead_index["LeadSampleSize"]),
                        "LeadOff": lead_index["LeadOff"],
                        "BaselineSway": lead_index["BaselineSway"],
                        "LeadDataCRC32": int(lead_index["LeadDataCRC32"])
                    }
                except KeyError as e:
                    print(f"Warning: Missing field {exception_message(e)} in lead data from ge for {lead_id}. Skipping this lead.")
                except Exception as e:
                    print(f"Error processing leads of ge {lead_id}: {exception_message(e)}")

    if leads["I"]["data"].size == leads["II"]["data"].size == 5000:  # derive additional leads
        leads["III"]["data"] = np.subtract(leads["II"]["data"], leads["I"]["data"])
        leads["aVR"]["data"] = np.add(leads["I"]["data"], leads["II"]["data"]) * (-0.5)
        leads["aVL"]["data"] = np.subtract(leads["I"]["data"], 0.5 * leads["II"]["data"])
        leads["aVF"]["data"] = np.subtract(leads["II"]["data"], 0.5 * leads["I"]["data"])

    for lead_id, lead_data in leads.items():  # validate lead data length
        if lead_data["data"].size != 5000 and lead_data["data"].size != 0:
            raise ValueError(f"Lead {lead_id} has incorrect data length: {lead_data['data'].size}")

    result = {
        "PatientID": patient_id,
        "Age": age,
        "Gender": gender,
        "SampleBase": sample_base, 
        "HighPassFilter": high_pass_filter, 
        "LowPassFilter": low_pass_filter,
        "Leads": leads
    }

    return result

def ge(xml_path):
    try:
        ecg_data = parse_ge_xml(xml_path)

        print("Basic information:")
        print(f"PatientID: {ecg_data.get('PatientID', '')}")
        print(f"Age: {ecg_data.get('Age', 'Unknown')}")
        print(f"Gender: {ecg_data.get('Gender', '')}")
        print(f"SampleBase: {ecg_data.get('SampleBase', '')}")
        print(f"HighPassFilter: {ecg_data.get('HighPassFilter', '')}")
        print(f"LowPassFilter: {ecg_data.get('LowPassFilter', '')}")

        print("\nLead information:")
        for lead_id, lead_data in ecg_data["Leads"].items():
            print(f"Lead: {lead_id}")
            print(f"Count of data: {len(lead_data['data'])}")
            print(f"Data: {lead_data['data']}")
            for key, value in lead_data["info"].items():
                print(f"{key}: {value}")
        
        print("\nWaveform processing information:")
        for lead_id in ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]:
            if lead_id in ecg_data["Leads"] and len(ecg_data["Leads"][lead_id]["data"]) > 0:
                print(f"Lead {lead_id} length: {len(ecg_data['Leads'][lead_id]['data'])}")
            else:
                print(f"Lead {lead_id} without valid data or length does not match.")

    except Exception as e:
        print(f"An error occurred during parsing: {exception_message(e)}")
        traceback.print_exc()

def ge_convert_to_matrix(xml_path):

    ecg_data = parse_ge_xml(xml_path)
    lead_names = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    lead_arrays = [np.array(ecg_data['Leads'][lead]['data']) for lead in lead_names if lead in ecg_data['Leads']]
    lengths = [len(data) for data in lead_arrays]  # make sure the length of all lead data is consistent and choose the shortest length to align the data
    min_length = min(lengths)
    lead_arrays = [data[:min_length] for data in lead_arrays]
    ecg_matrix = np.column_stack(lead_arrays)
    print(f"Original matrix shape: {ecg_matrix.shape}")
    ecg_matrix = resample_ecg_matrix(ecg_matrix)
    print(f"Resample matrix shape:{ecg_matrix.shape}")
    return ecg_matrix

## philips ##
def parse_philips_svg(svg_path):

    lead_name = {'leadI': 'leadI', 'leadII': 'leadII', 'leadIII': 'leadIII', 'leadaVR': 'leadaVR', 'leadaVL': 'leadaVL', 'leadaVF': 'leadaVF', 'leadV1': 'leadV1', 'leadV2': 'leadV2', 'leadV3': 'leadV3', 'leadV4': 'leadV4', 'leadV5': 'leadV5', 'leadV6': 'leadV6'}
    ecg_wave_data = {}

    raw_svg = ET.parse(svg_path).getroot()
    for root in raw_svg.findall("{http://www.w3.org/2000/svg}g"):
        if root.attrib["id"] == "waveformSegment":
            for child in root:
                if child.attrib["id"] in lead_name.keys():
                    current_lead_name = lead_name[child.attrib["id"]]
                    for sub_child in child.findall("{http://www.w3.org/2000/svg}path"):
                        if sub_child.attrib["id"] == "wavedata":
                            raw_ecg = sub_child.attrib["d"].split(" ")[4:]
                            raw_value = raw_ecg[1::2]
                            ecg_wave_data[current_lead_name] = np.array(raw_value, dtype="float64") * -1

    leads_matrix = [np.array(data) for data in ecg_wave_data.values()]
    ecg_matrix = np.stack(leads_matrix, axis=-1)
    ecg_matrix = resample_ecg_matrix(ecg_matrix)
    return ecg_matrix

def parse_philips_xml(xml_path):

    namespace = {"philips": "http://www3.medical.philips.com"}

    root = ET.parse(xml_path).getroot()

    doc_info = root.find("philips:documentinfo", namespace)  # parse basic information 
    document_data = {
        "document_name": doc_info.find("philips:documentname", namespace).text if doc_info.find("philips:documentname", namespace) is not None else "",
        "filename": doc_info.find("philips:filename", namespace).text if doc_info.find("philips:filename", namespace) is not None else "",
        "document_type": doc_info.find("philips:documenttype", namespace).text if doc_info.find("philips:documenttype", namespace) is not None else "",
        "document_version": doc_info.find("philips:documentversion", namespace).text if doc_info.find("philips:documentversion", namespace) is not None else ""
    }

    patient = root.find("philips:patient", namespace)  # parse patient information 
    patient_data = {}
    if patient is not None:
        general_patient = patient.find("philips:generalpatientdata", namespace)
        if general_patient is not None:
            for child in general_patient:
                tag = child.tag.split("}")[-1]
                patient_data[tag] = child.text

    waveforms = root.find("philips:waveforms", namespace)  # parse waveform parameters
    parsed_waveforms = waveforms.find("philips:parsedwaveforms", namespace)
    waveform_params = parsed_waveforms.attrib
    leads_info = {
        "compress_flag": waveform_params.get("compressflag"),
        "compress_method": waveform_params.get("compressmethod").split(),
        "data_encoding": waveform_params.get("dataencoding"),
        "duration_per_channel": waveform_params.get("durationperchannel"),
        "nbits_per_sample": waveform_params.get("nbitspersample")
    }

    xml_ecgs = SPxml.getLeads(xml_path)  # parse rhythm information
    for ecg in xml_ecgs:
        [float(i) for i in ecg["data"]]
        ecg["data"] = np.asarray(ecg["data"], dtype='float64')
    
    repbeats = waveforms.find('philips:repbeats', namespace)
    rhythm_data = []
    if repbeats is not None:
        for index, repbeat in enumerate(repbeats.findall('philips:repbeat', namespace)):
            rhythm_data.append(
                {
                    'ecg_data': xml_ecgs[index]["data"],
                    'lead_name': repbeat.get('leadname'),
                    'duration': repbeat.get('duration'),
                    'ponset': repbeat.get('ponset'),
                    'pend': repbeat.get('pend'),
                    'qonset': repbeat.get('qonset'),
                    'qend': repbeat.get('qend'),
                    'tonset': repbeat.get('tonset'),
                    'tend': repbeat.get('tend'),
                }
            )
    
    waveform_base64 = parsed_waveforms.text  # decode waveform data
    decode_data = base64.b64decode(waveform_base64)
    waveform_data = np.frombuffer(decode_data, dtype=np.int16)

    return {
        'document_info': document_data,
        'patient_info': patient_data,
        'waveform_params': waveform_params,
        'leads_info': leads_info,
        'rhythm_data': rhythm_data,
        'raw_waveform_data': waveform_data
    }

def philips(xml_path):
    try:
        ecg_data = parse_philips_xml(xml_path)

        print("\nDocument information:")
        for key, value in ecg_data['document_info'].items():
            print(f"{key}: {value}")
        
        print("\nPatient information:")
        for key, value in ecg_data['patient_info'].items():
            print(f"{key}: {value}")
        
        print("\nLead information:")
        for key, value in ecg_data['leads_info'].items():
            print(f"{key}: {value}")
        
        print("\nRhythm information:")
        for index, rhythm in enumerate(ecg_data['rhythm_data']):
            print(f"Lead {index + 1}:")
            for key, value in rhythm.items():
                print(f"  {key}: {value}")
        
        print("\nWaveform information:")
        print(f"waveform data shape: {ecg_data['raw_waveform_data'].shape}")
        print(f"waveform data type: {ecg_data['raw_waveform_data'].dtype}")
    
    except Exception as e:
        print(f"An error occurred during parsing: {exception_message(e)}")
        traceback.print_exc()

def philips_convert_to_matrix(xml_path):

    xml_ecgs = SPxml.getLeads(xml_path)
    lead_data = [np.asarray(ecg["data"], dtype='float64') for ecg in xml_ecgs]
    ecg_matrix = np.stack(lead_data, axis=-1)
    print(f"Original matrix shape: {ecg_matrix.shape}")
    ecg_matrix = resample_ecg_matrix(ecg_matrix)
    print(f"Resample matrix shape:{ecg_matrix.shape}")
    return ecg_matrix

if __name__ == "__main__":

    ## ge ##
    # xml_path = "/home/young19990726/Project/smart-app/backend/app/misc/utils/file/MUSE_162803_13000.xml"
    # parse_ge_xml(xml_path)
    # ge(xml_path)
    # ecg_matrix = ge_convert_to_matrix(xml_path)
    # print(ecg_matrix)

    ## philips ##
    # svg: 1*12 #
    # svg_path = "/home/young19990726/Project/smart-app/backend/app/misc/utils/file/PageWriterTouchECG2013128141153817.svg"
    # ecg_matrix = parse_philips_svg(svg_path)
    # print(ecg_matrix)

    # xml #
    # xml_path = "/home/young19990726/Project/smart-app/backend/app/misc/utils/file/PageWriterTouchECG2013128141153817.xml"
    # parse_philips_xml(xml_path)
    # philips(xml_path)
    # ecg_matrix = philips_convert_to_matrix(xml_path)
    # print(ecg_matrix)

    # ai analysis #
    # matrix_data = ecg_matrix.T
    # result = ecg_ai_model(matrix_data)
    # print(result)

    pass