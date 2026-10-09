# SIT225 Pass Task 4 (4P) - resubmission files

Chakriya Thida An (224753555)

This repository holds the files requested in the 4P resubmission feedback.

| Requested | File(s) |
|---|---|
| Report (Parts 1-3, Week 8 activity sheets, certificate) | `SIT225_4P_Report_Resubmission.pdf` |
| Makerspace soldering induction certificate | `Makerspace_Soldering_Certificate.pdf` (also Appendix C of the report) |
| Raw data | `4P_code_and_data/raw_data.csv` |
| Processed data | `4P_code_and_data/processed_data.csv` |
| Arduino sketch | `4P_code_and_data/dht22_firebase/dht22_firebase.ino` |
| Python scripts | `4P_code_and_data/live_monitor.py` (ingestion), `process.py` (raw to processed), `analysis.py` (statistics and plots), `config.py` (shared settings) |
| Week 8 Activity 8.2: Python scripts | `Week8_Activity_8.2/accelerometer_separate_files.py`, `Week8_Activity_8.2/accelerometer_single_file.py` |
| Week 8 Activity 8.2: three individual CSV files | `Week8_Activity_8.2/accelerometer_x.csv`, `accelerometer_y.csv`, `accelerometer_z.csv` |
| Week 8 Activity 8.2: combined CSV file | `Week8_Activity_8.2/accelerometer_xyz.csv` |

## Pipeline

DHT22 -> Arduino Nano 33 IoT -> WiFi -> Firebase -> `live_monitor.py` -> `raw_data.csv` -> `process.py` -> `processed_data.csv` -> `analysis.py`

From inside `4P_code_and_data/`:

```
python3 process.py     # raw_data.csv -> processed_data.csv + data_quality_report.txt
python3 analysis.py    # processed_data.csv -> statistics, hypothesis tests and plots
```

Credentials (WiFi, Firebase and Arduino Cloud keys) have been removed from this repository.
