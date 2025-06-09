# from NanoVNASaver.Serial import Interface
# from NanoVNASaver.Hardware import get_VNA
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import csv
import math
from Serial import Interface
from Hardware import get_VNA


def save_and_print_s21():
    DataS21 = []
    radar = Interface("serial", "S-A-A-2")
    radar.port = "COM6" 
    radar.open()

    vna = get_VNA(radar)
    frequencies = vna.readFrequencies()
    values11 = vna.readValues("data 0")
    values21 = vna.readValues("data 1")


    print("Freq =", frequencies)
    print("Data S11=",values11)
    print("Data S21=",values21)

    DataS21.append(values21)
    # print("Data Raw = ", DataS21)

    # data_s21_float = [[float(num) for item in sublist for num in item.split()] for sublist in DataS21]

    # Convert to a numpy array
    # data_array = np.array(data_s21_float)

    # print("Data Array = ", data_array)

    # Reshape the array to have two columns: one for real parts and one for imaginary parts
    # data_array = data_array.reshape(-1, 2)
    # print(data_array)

    # Extract real and imaginary parts
    # data_real = data_array[:, 0]  # First column for real parts
    # data_imaginary = data_array[:, 1]  # Second column for imaginary parts




    # Combine into complex numbers
    # s21_save = complex(data_real,data_imaginary)
    # s21 = data_real + 1j * data_imaginary
    # mag = 20*math.log10(abs(s21))

    # # Print all the complex numbers
    # # print(s21)
    # # print(len(s21))

    # Nfft = 512

    # N = len(s21)
    # k = 1

    # Sfft = np.zeros(Nfft, dtype=complex)

    # Sfft[0:k] = 0
    # Sfft[k:N+k] = s21[0:N]
    # Sfft[N+k:Nfft-N-k] = 0  # Zero padding
    # Sfft[Nfft-N-k:Nfft-k] = np.conjugate(s21[::-1])
    # Sfft[Nfft-k:Nfft] = 0

    # St = np.real(np.fft.ifft(Sfft))

    # fmin = 10000
    # fmax = 6000e6
    # deltaf=(fmax-fmin)/Nfft
    # fm=N*deltaf/2
    # fs=1.5*fm*1e6
    # t = np.arange(0, (1/fs) * Nfft, 1/fs)
    # t = t - 5 * 1e-9 * np.ones(len(t))
    # tt = t * t
    # a=0.4*1e-9
    # x = (-1 / (a * np.sqrt(2 * np.pi))) * (1 / a**2) * t * np.exp(-tt / (2 * a**2))

    # x = x / np.max(x) # Normalize x by dividing by its maximum value

    # y = x[:Nfft]

    # sfftx = np.fft.fft(y)

    # Sfrec = sfftx * Sfft

    # Strec = -np.real(np.fft.ifft(Sfrec))

    # # nd = np.abs(Strec / np.max(np.abs(Strec)) - x / np.max(np.abs(x)))
    # nd = Strec / np.max(Strec) - x / np.max(x)
    # # nd = nd+1
    # # nd = nd / np.max(nd)

    # print(nd)

    # x_data = np.arange(len(nd))

    # # Plot the data
    # plt.figure(figsize=(10, 6))
    # plt.plot(x_data, np.abs(nd), label='test data')

    # plt.xlabel('FFT Sample Index')
    # plt.ylabel('Amplitude Value of |S21|')
    # plt.title('Plot S21 Parameter')
    # plt.legend()
    # plt.grid(True)

    # plt.show()

    # plt.figure(figsize=(10, 6))
    # # plt.plot(x_data, nd, label='test data')
    # plt.plot(mag, label='test data')

    # plt.xlabel('FFT Sample Index')
    # plt.ylabel('Amplitude Value of |S21|')
    # plt.title('Magnitude')
    # plt.legend()
    # plt.grid(True)

    # # Set the limits for y-axis
    # # plt.ylim([0, max(nd)])

    # plt.show()

    # # Prepare data for CSV
    #   data_for_csv = np.column_stack((data_real, data_imaginary))

    #   # Create a DataFrame
    #   df = pd.DataFrame(data_for_csv)

    #   # Save DataFrame to CSV without header
    #   df.to_csv("s21_data_pakealuminium.csv", index=False, header=False)

    #   print("Data saved to s21_data.csv without header")


    # float_pairs = []
    # import csv
    # # Process each string in the list
    # for data in values21:
    #     # Split by space and convert to float
    #     pair = [float(x) for x in data.split()]
    #     # Add the pair to the list
    #     float_pairs.append(pair)

    # # Print the resulting list of float pairs
    # for i, pair in enumerate(float_pairs):
    #     print(f"{pair[0]}, {pair[1]}")

    # with open('./12Juni2024/data1Aluminium4.csv', 'w', newline='') as csvfile:
    #     csvwriter = csv.writer(csvfile)
    #     # csvwriter.writerow(['Value1', 'Value2'])  # Write header
    #     csvwriter.writerows(float_pairs)  # Write data

    # print("Data has been saved to float_pairs.csv")

    # with open('./12Juni2024/data1Aluminium4.csv', 'w', newline='') as csvfile:
    #     writer = csv.writer(csvfile)
    #     for row in s21_save:
    #         writer.writerow(row)

    # print("Data saved to s21_data.csv without header")


# This block ensures the function runs only when the script is executed directly
if __name__ == "__main__":
  save_and_print_s21()
  # Get the filename from user input
  


# data_s21_float = [list(map(float, item.split())) for item in DataS21]
# data_array = np.array(data_s21_float)

# # Extract real and imaginary parts
# data_real = data_array[:, 0]  # First column for real parts
# data_imaginary = data_array[:, 1]  # Second column for imaginary parts

# # Combine into complex numbers
# s21 = data_real + 1j * data_imaginary

# print(s21)
# print(len(s21))