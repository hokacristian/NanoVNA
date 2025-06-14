import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import csv
import math
import json
import time
import signal
import sys
from datetime import datetime
from NanoVNASaver.Serial import Interface
from NanoVNASaver.Hardware import get_VNA

# Supabase integration
from supabase import create_client, Client
import os
from typing import List, Dict, Any

# GPIO untuk button trigger
import RPi.GPIO as GPIO

class NanoVNASupabaseLogger:
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client
        """
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.table_name = "nanovna_measurements"
        
    def insert_measurement_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        Insert measurement data to Supabase with batch processing
        """
        try:
            # Insert dalam batch untuk handle large datasets
            batch_size = 100
            total_inserted = 0
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                # Clean data - pastikan tidak ada NaN atau None
                cleaned_batch = []
                for record in batch:
                    cleaned_record = {}
                    for key, value in record.items():
                        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                            cleaned_record[key] = 0.0  # Replace NaN/Inf dengan 0
                        else:
                            cleaned_record[key] = value
                    cleaned_batch.append(cleaned_record)
                
                result = self.supabase.table(self.table_name).insert(cleaned_batch).execute()
                total_inserted += len(cleaned_batch)
                print(f"✅ Inserted batch {i//batch_size + 1}: {len(cleaned_batch)} records")
            
            print(f"🎉 Total successfully inserted: {total_inserted} records")
            return True
            
        except Exception as e:
            print(f"❌ Error inserting data to Supabase: {e}")
            return False

class ButtonTrigger:
    def __init__(self, pin=17, callback=None):
        """
        Initialize button trigger on specified GPIO pin
        """
        self.pin = pin
        self.callback = callback
        self.setup_gpio()
        
    def setup_gpio(self):
        """
        Setup GPIO untuk button
        """
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Setup interrupt untuk button press
            GPIO.add_event_detect(
                self.pin, 
                GPIO.FALLING,  # Trigger saat button ditekan (LOW)
                callback=self.button_pressed,
                bouncetime=2000  # Debounce 2 detik untuk menghindari multiple trigger
            )
            print(f"✅ Button trigger setup on GPIO pin {self.pin}")
            
        except Exception as e:
            print(f"❌ Error setting up GPIO: {e}")
            
    def button_pressed(self, channel):
        """
        Callback saat button ditekan
        """
        print(f"\n🔴 BUTTON PRESSED! Triggering NanoVNA measurement...")
        if self.callback:
            self.callback()
            
    def cleanup(self):
        """
        Cleanup GPIO
        """
        GPIO.cleanup()
        print("🧹 GPIO cleaned up")

def read_nanovna_real_data():
    """
    Membaca data ASLI dari hardware NanoVNA
    """
    print("🔌 CONNECTING TO NANOVNA HARDWARE...")
    
    # ============ KONFIGURASI NANOVNA ============
    COM_PORT = "/dev/ttyACM0"  # 🔧 Port untuk Raspberry Pi
    
    # ============ KONFIGURASI FREKUENSI ============
    # Range frekuensi yang akan dibaca dan disimpan
    FREQ_START = 2000000000   # 2.0 GHz 
    FREQ_STOP = 3000000000    # 3.0 GHz
    
    # Range yang akan difilter untuk database (sesuai permintaan Anda)
    FREQ_MIN_DB = 2400000000  # 2.4 GHz - minimum untuk database
    FREQ_MAX_DB = 2450000000  # 2.45 GHz - maximum untuk database
    
    print(f"📡 NanoVNA Port: {COM_PORT}")
    print(f"🎯 Sweep Range: {FREQ_START/1e9:.1f} - {FREQ_STOP/1e9:.1f} GHz")
    print(f"💾 Database Range: {FREQ_MIN_DB/1e9:.1f} - {FREQ_MAX_DB/1e9:.1f} GHz")
    
    try:
        # ============ KONEKSI KE NANOVNA ============
        print("\n🔗 Initializing NanoVNA connection...")
        radar = Interface("serial", "S-A-A-2")
        radar.port = COM_PORT
        radar.open()
        print("✅ Serial connection established")
        
        # Get VNA instance
        vna = get_VNA(radar)
        print("✅ VNA instance created")
        
        # ============ SET SWEEP PARAMETERS ============
        print(f"⚙️ Setting sweep range: {FREQ_START/1e9:.1f} - {FREQ_STOP/1e9:.1f} GHz")
        vna.setSweep(int(FREQ_START), int(FREQ_STOP))
        
        # ============ READ DATA FROM NANOVNA ============
        print("📊 Reading frequencies from NanoVNA...")
        frequencies = vna.readFrequencies()
        print(f"✅ Read {len(frequencies)} frequency points")
        
        print("📊 Reading S11 data from NanoVNA...")
        values11 = vna.readValues("data 0")  # S11 data
        print(f"✅ Read {len(values11)} S11 data points")
        
        print("📊 Reading S21 data from NanoVNA...")
        values21 = vna.readValues("data 1")  # S21 data  
        print(f"✅ Read {len(values21)} S21 data points")
        
        # ============ CLOSE CONNECTION ============
        radar.close()
        print("✅ NanoVNA connection closed")
        
        # ============ DISPLAY ACTUAL RANGE ============
        actual_start = frequencies[0] if frequencies else 0
        actual_stop = frequencies[-1] if frequencies else 0
        print(f"📈 Actual frequency range: {actual_start/1e9:.3f} - {actual_stop/1e9:.3f} GHz")
        
        return frequencies, values11, values21, FREQ_MIN_DB, FREQ_MAX_DB
        
    except Exception as e:
        print(f"❌ Error reading from NanoVNA: {e}")
        print("💡 Troubleshooting:")
        print(f"   - Cek apakah NanoVNA terhubung ke port {COM_PORT}")
        print("   - Cek apakah driver NanoVNA sudah terinstall")
        print("   - Coba ganti port (/dev/ttyUSB0, /dev/ttyUSB1, dll)")
        print("   - Pastikan NanoVNA tidak digunakan aplikasi lain")
        return None

def process_nanovna_data(frequencies, values11, values21, freq_min, freq_max):
    """
    Process data NanoVNA dan filter sesuai range yang diinginkan
    """
    print(f"\n🔄 PROCESSING NANOVNA DATA...")
    
    # Generate session ID
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"📅 Session ID: {session_id}")
    
    # Filter dan process data
    all_data = []
    filtered_data = []
    
    print(f"🔍 Processing {len(frequencies)} data points...")
    
    for i, freq in enumerate(frequencies):
        try:
            # Parse S11 data (format: "real imag")
            s11_parts = values11[i].split()
            s11_real = float(s11_parts[0])
            s11_imag = float(s11_parts[1])
            
            # Parse S21 data (optional, untuk record lengkap)
            s21_parts = values21[i].split() if i < len(values21) else ["0", "0"]
            s21_real = float(s21_parts[0])
            s21_imag = float(s21_parts[1])
            
            # Hitung parameter S11
            s11_magnitude = math.sqrt(s11_real**2 + s11_imag**2)
            return_loss_db = 20 * math.log10(s11_magnitude) if s11_magnitude > 0 else -100
            vswr = (1 + s11_magnitude) / (1 - s11_magnitude) if s11_magnitude < 1 else 999
            phase_degrees = math.degrees(math.atan2(s11_imag, s11_real))
            
            # Buat record lengkap
            record = {
                "frequency": int(freq),
                "s11_real": s11_real,
                "s11_imag": s11_imag,
                "s11_magnitude": s11_magnitude,
                "return_loss_db": return_loss_db,
                "vswr": vswr,
                "phase_degrees": phase_degrees,
                "session_id": session_id,
                "notes": f"NanoVNA measurement at {freq/1e9:.3f} GHz"
            }
            
            all_data.append(record)
            
            # Filter untuk database (hanya range yang diinginkan)
            if freq_min <= freq <= freq_max:
                filtered_data.append(record)
                
                # Print format yang diminta
                print(f"{int(freq)};{s11_real:.12e};{s11_imag:.12e}")
                
        except (ValueError, IndexError) as e:
            print(f"⚠️ Error processing data point {i}: {e}")
            continue
    
    print(f"\n📊 DATA SUMMARY:")
    print(f"   Total points processed: {len(all_data)}")
    print(f"   Filtered for database: {len(filtered_data)}")
    print(f"   Frequency range (all): {frequencies[0]/1e9:.3f} - {frequencies[-1]/1e9:.3f} GHz")
    print(f"   Frequency range (filtered): {freq_min/1e9:.3f} - {freq_max/1e9:.3f} GHz")
    
    return all_data, filtered_data, session_id

def analyze_data(data):
    """
    Analisis cepat data yang dibaca
    """
    if not data:
        return
        
    print(f"\n📈 QUICK ANALYSIS:")
    
    frequencies = [d["frequency"] for d in data]
    return_losses = [d["return_loss_db"] for d in data]
    vswrs = [d["vswr"] for d in data]
    
    # Find best performance
    best_rl_idx = return_losses.index(min(return_losses))
    best_freq = frequencies[best_rl_idx]
    best_rl = return_losses[best_rl_idx]
    best_vswr = vswrs[best_rl_idx]
    
    print(f"   📊 Frequency range: {min(frequencies)/1e9:.3f} - {max(frequencies)/1e9:.3f} GHz")
    print(f"   🎯 Best return loss: {best_rl:.2f} dB at {best_freq/1e9:.3f} GHz")
    print(f"   📈 Best VSWR: {best_vswr:.2f}")
    print(f"   📊 Average return loss: {sum(return_losses)/len(return_losses):.2f} dB")
    
    # Performance categories
    excellent = len([rl for rl in return_losses if rl < -20])
    good = len([rl for rl in return_losses if -20 <= rl < -15])
    acceptable = len([rl for rl in return_losses if -15 <= rl < -10])
    poor = len([rl for rl in return_losses if rl >= -10])
    
    print(f"   📈 Performance distribution:")
    print(f"      🎯 Excellent (< -20 dB): {excellent} points")
    print(f"      ✅ Good (-15 to -20 dB): {good} points")
    print(f"      📊 Acceptable (-10 to -15 dB): {acceptable} points")
    print(f"      ⚠️ Poor (> -10 dB): {poor} points")

def send_to_supabase(data: List[Dict], session_id: str):
    """
    Kirim data ke Supabase database
    """
    print(f"\n📤 SENDING DATA TO SUPABASE...")
    
    # ============ KONFIGURASI SUPABASE ============
    # 🔧 GANTI dengan credentials Anda
    SUPABASE_URL = "https://bxqetstclndccppyalom.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ4cWV0c3RjbG5kY2NwcHlhbG9tIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTQ4MjM1MCwiZXhwIjoyMDY1MDU4MzUwfQ.3ZbX9aiIpHqpSKmOyyvAEhd9FuJ_jmPB_xdIOBrI3SQ"
    
    # Atau baca dari environment variables (lebih aman)
    SUPABASE_URL = os.getenv("SUPABASE_URL", SUPABASE_URL)
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", SUPABASE_KEY)
    
    try:
        # Initialize Supabase client
        db_logger = NanoVNASupabaseLogger(SUPABASE_URL, SUPABASE_KEY)
        
        # Insert data
        success = db_logger.insert_measurement_data(data)
        
        if success:
            print(f"🎉 Data berhasil dikirim ke Supabase!")
            print(f"📅 Session ID: {session_id}")
            print(f"📊 Total records: {len(data)}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Error in Supabase integration: {e}")
        return False

def plot_results(data):
    """
    Plot hasil pengukuran (optional - bisa dihidupkan jika ada display)
    """
    if not data or len(data) < 2:
        print("⚠️ Insufficient data for plotting")
        return
        
    print(f"\n📊 GENERATING PLOTS...")
    
    frequencies = [d["frequency"]/1e9 for d in data]  # Convert to GHz
    return_losses = [d["return_loss_db"] for d in data]
    vswrs = [d["vswr"] for d in data]
    phases = [d["phase_degrees"] for d in data]
    
    # Create plots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # Return Loss
    ax1.plot(frequencies, return_losses, 'b-', linewidth=2)
    ax1.set_xlabel('Frequency (GHz)')
    ax1.set_ylabel('Return Loss (dB)')
    ax1.set_title('S11 Return Loss vs Frequency')
    ax1.grid(True)
    ax1.set_ylim(max(return_losses) + 5, min(return_losses) - 5)
    
    # VSWR
    ax2.plot(frequencies, vswrs, 'r-', linewidth=2)
    ax2.set_xlabel('Frequency (GHz)')
    ax2.set_ylabel('VSWR')
    ax2.set_title('VSWR vs Frequency')
    ax2.grid(True)
    ax2.set_ylim(1, min(10, max(vswrs)))
    
    # Phase
    ax3.plot(frequencies, phases, 'g-', linewidth=2)
    ax3.set_xlabel('Frequency (GHz)')
    ax3.set_ylabel('Phase (degrees)')
    ax3.set_title('S11 Phase vs Frequency')
    ax3.grid(True)
    
    # S11 Magnitude
    s11_mags = [d["s11_magnitude"] for d in data]
    ax4.plot(frequencies, s11_mags, 'm-', linewidth=2)
    ax4.set_xlabel('Frequency (GHz)')
    ax4.set_ylabel('S11 Magnitude')
    ax4.set_title('S11 Magnitude vs Frequency')
    ax4.grid(True)
    
    plt.tight_layout()
    
    # Save plot instead of showing (headless mode)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nanovna_plot_{timestamp}.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"📊 Plot saved to: {filename}")
    plt.close()  # Close figure to free memory

def run_nanovna_measurement():
    """
    Fungsi utama untuk membaca data dari NanoVNA dan kirim ke database
    Dipanggil saat button ditekan
    """
    print("\n" + "="*60)
    print("🚀 STARTING NANOVNA MEASUREMENT SESSION")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # 1. Baca data ASLI dari NanoVNA hardware
        result = read_nanovna_real_data()
        if result is None:
            print("❌ Gagal membaca data dari NanoVNA hardware")
            return False
        
        frequencies, values11, values21, freq_min, freq_max = result
        
        # 2. Process dan filter data
        all_data, filtered_data, session_id = process_nanovna_data(
            frequencies, values11, values21, freq_min, freq_max
        )
        
        if len(filtered_data) == 0:
            print("⚠️ Tidak ada data dalam range frekuensi yang ditentukan")
            return False
        
        # 3. Analisis data
        analyze_data(filtered_data)
        
        # 4. Langsung kirim ke Supabase (tanpa konfirmasi)
        print(f"\n🚀 AUTO-SENDING TO DATABASE:")
        print(f"   📊 {len(filtered_data)} data points")
        print(f"   📅 Session ID: {session_id}")
        print(f"   📈 Frequency range: {freq_min/1e9:.1f} - {freq_max/1e9:.1f} GHz")
        
        success = send_to_supabase(filtered_data, session_id)
        
        if success:
            print("✅ SUCCESS! Data berhasil disimpan ke database!")
            
            # 5. Save backup file
            backup_filename = f"nanovna_backup_{session_id}.json"
            with open(backup_filename, 'w') as f:
                json.dump(filtered_data, f, indent=2)
            print(f"💾 Backup saved: {backup_filename}")
            
            # 6. Optional: Generate plot (headless mode)
            try:
                plot_results(filtered_data)
            except Exception as plot_error:
                print(f"⚠️ Plot generation failed: {plot_error}")
            
            return True
        else:
            print("❌ Gagal menyimpan ke database!")
            return False
            
    except Exception as e:
        print(f"❌ Error in measurement session: {e}")
        return False

def signal_handler(sig, frame):
    """
    Handle Ctrl+C untuk graceful shutdown
    """
    print('\n🛑 Shutdown signal received...')
    cleanup_and_exit()

def cleanup_and_exit():
    """
    Cleanup resources dan exit
    """
    global button_trigger
    try:
        if 'button_trigger' in globals():
            button_trigger.cleanup()
        print("🧹 Cleanup completed")
    except:
        pass
    print("👋 Goodbye!")
    sys.exit(0)

def main():
    """
    Main program - setup button trigger dan wait for button press
    """
    global button_trigger
    
    print("🚀 NANOVNA AUTO DATA LOGGER")
    print("=" * 50)
    print("📌 Button trigger on GPIO pin 17")
    print("🔴 Press the button to start measurement")
    print("⌨️  Press Ctrl+C to exit")
    print("=" * 50)
    
    # Setup signal handler untuk Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup button trigger
        button_trigger = ButtonTrigger(pin=17, callback=run_nanovna_measurement)
        
        print("✅ System ready! Waiting for button press...")
        print("💡 Status: Idle - Press button to trigger measurement")
        
        # Main loop - wait for button press
        while True:
            time.sleep(1)  # Sleep untuk mengurangi CPU usage
            
    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected")
        cleanup_and_exit()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        cleanup_and_exit()

if __name__ == "__main__":
    main()