import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import csv
import math
from NanoVNASaver.Serial import Interface
from NanoVNASaver.Hardware import get_VNA

def read_nanovna_2_3ghz():
    """
    Membaca data S11 dari NanoVNA dalam range 2-3 GHz
    Output format: frequency; S11_real; S11_imag
    """
    
    # Inisialisasi koneksi NanoVNA
    radar = Interface("serial", "S-A-A-2")
    radar.port = "COM3"  # Sesuaikan dengan port Anda
    radar.open()

    # Get VNA instance
    vna = get_VNA(radar)
    
    # Set frekuensi range: 2 GHz - 3 GHz
    start_freq = 2e9  # 2 GHz dalam Hz
    stop_freq = 3e9   # 3 GHz dalam Hz
    
    print(f"Setting frequency range: {start_freq/1e9:.1f} GHz - {stop_freq/1e9:.1f} GHz")
    
    # Set sweep frequency range
    vna.setSweep(int(start_freq), int(stop_freq))
    
    # Baca data frekuensi dan S11
    frequencies = vna.readFrequencies()
    values11 = vna.readValues("data 0")  # S11 data
    
    print(f"Frequency points: {len(frequencies)}")
    print(f"S11 data points: {len(values11)}")
    
    # Tampilkan range frekuensi yang terbaca
    print(f"Actual frequency range: {frequencies[0]/1e9:.3f} GHz - {frequencies[-1]/1e9:.3f} GHz")
    
    # Process dan tampilkan data
    print("\n=== DATA FORMAT: FREQUENCY; S11_REAL; S11_IMAG ===")
    
    # List untuk menyimpan data
    csv_data = []
    
    for i, freq in enumerate(frequencies):
        # Parse S11 data (format: "real imag")
        s11_parts = values11[i].split()
        s11_real = float(s11_parts[0])
        s11_imag = float(s11_parts[1])
        
        # Format output seperti yang diminta: frequency; real; imag
        output_line = f"{int(freq)};{s11_real:15.12e};{s11_imag:15.12e}"
        print(output_line)
        
        # Simpan untuk CSV
        csv_data.append([int(freq), s11_real, s11_imag])
    
    # Simpan ke file CSV
    output_filename = "nanovna_2_3ghz_s11_data.csv"
    with open(output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        for row in csv_data:
            writer.writerow([row[0], f"{row[1]:.12e}", f"{row[2]:.12e}"])
    
    print(f"\nData saved to: {output_filename}")
    
    # Analisis cepat: cari return loss minimum
    print("\n=== QUICK ANALYSIS ===")
    min_return_loss = float('inf')
    best_freq = 0
    best_s11 = (0, 0)
    
    for i, freq in enumerate(frequencies):
        s11_parts = values11[i].split()
        s11_real = float(s11_parts[0])
        s11_imag = float(s11_parts[1])
        
        # Hitung return loss
        s11_magnitude = math.sqrt(s11_real**2 + s11_imag**2)
        return_loss = 20 * math.log10(s11_magnitude)
        
        if return_loss < min_return_loss:
            min_return_loss = return_loss
            best_freq = freq
            best_s11 = (s11_real, s11_imag)
    
    print(f"Best return loss: {min_return_loss:.2f} dB at {best_freq/1e9:.3f} GHz")
    print(f"S11 at best point: {best_s11[0]:.6e} {best_s11[1]:+.6e}j")
    
    # Tutup koneksi
    radar.close()
    
    return csv_data

def analyze_s11_data(csv_data):
    """
    Analisis tambahan untuk data S11
    """
    print("\n=== DETAILED ANALYSIS ===")
    
    return_losses = []
    frequencies = []
    
    for freq, s11_real, s11_imag in csv_data:
        s11_magnitude = math.sqrt(s11_real**2 + s11_imag**2)
        return_loss = 20 * math.log10(s11_magnitude)
        
        return_losses.append(return_loss)
        frequencies.append(freq/1e9)  # Convert to GHz
    
    # Plot hasil
    plt.figure(figsize=(12, 6))
    
    plt.subplot(1, 2, 1)
    plt.plot(frequencies, return_losses, 'b-', linewidth=2)
    plt.xlabel('Frequency (GHz)')
    plt.ylabel('Return Loss (dB)')
    plt.title('S11 Return Loss vs Frequency')
    plt.grid(True)
    
    # Cari dan tandai titik minimum
    min_idx = return_losses.index(min(return_losses))
    plt.plot(frequencies[min_idx], return_losses[min_idx], 'ro', markersize=8, 
             label=f'Min: {return_losses[min_idx]:.2f} dB @ {frequencies[min_idx]:.3f} GHz')
    plt.legend()
    
    # Plot VSWR
    plt.subplot(1, 2, 2)
    vswr_values = []
    for rl in return_losses:
        reflection_coef = 10**(rl/20)  # Convert dB back to linear
        vswr = (1 + reflection_coef) / (1 - reflection_coef)
        vswr_values.append(vswr)
    
    plt.plot(frequencies, vswr_values, 'r-', linewidth=2)
    plt.xlabel('Frequency (GHz)')
    plt.ylabel('VSWR')
    plt.title('VSWR vs Frequency')
    plt.grid(True)
    plt.ylim(1, 5)  # Limit VSWR range for better visualization
    
    plt.tight_layout()
    plt.show()
    
    return frequencies, return_losses

# Fungsi utama yang dimodifikasi
def save_and_print_s11_modified():
    """
    Fungsi utama yang dimodifikasi untuk membaca 2-3 GHz
    dan menghasilkan output dalam format yang diminta
    """
    try:
        # Baca data dari NanoVNA
        csv_data = read_nanovna_2_3ghz()
        
        # Analisis data (opsional)
        analyze_s11_data(csv_data)
        
        print("\n✅ SUCCESS: Data berhasil dibaca dan disimpan!")
        print("Format output: frequency; S11_real; S11_imag")
        print("Contoh: 2450000000;-6.170969456e-03;-5.002862215e-02")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Pastikan:")
        print("1. NanoVNA terhubung ke port yang benar")
        print("2. Driver NanoVNA terinstall")
        print("3. Port COM sesuai (ubah di line radar.port)")

# Script execution
if __name__ == "__main__":
    print("🔧 NanoVNA 2-3 GHz S11 Data Reader")
    print("=" * 50)
    save_and_print_s11_modified()