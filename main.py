import os
import csv
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports
import pandas as pd
import time

def list_ports():
    """Zwraca listę dostępnych portów USB."""
    return [port.device for port in serial.tools.list_ports.comports()]

def fetch_data_from_arduino(port):
    """Pobiera dane z Arduino."""
    try:
        with serial.Serial(port, 9600, timeout=10) as ser:
            time.sleep(2)  # Czeka na zakończenie resetu Arduino
            ser.write(b"T")  # Wysyła 'T' do Arduino w celu żądania danych

            received_data = ""
            while True:
                line = ser.readline().decode().strip()  # Odczytuje linię
                if line == "#":  # Koniec transmisji
                    break
                received_data += line + "\n"
            return received_data
    except Exception as e:
        messagebox.showerror("Błąd", f"Nie udało się nawiązać komunikacji z Arduino: {e}")
        return ""

def save_data_to_csv(data):
    """Zapisuje dane do plików CSV, dzieląc je według dni."""
    rows = data.splitlines()
    daily_data = {}

    for row in rows:
        parts = row.split(",")
        if len(parts) == 8:  # Upewnij się, że wiersz ma odpowiednią liczbę elementów
            # Dodawanie zer wiodących do daty
            date = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(parts)

    for date, entries in daily_data.items():
        file_name = f"data_{date}.csv"
        file_path = os.path.join(os.getcwd(), file_name)

        if not os.path.exists(file_path):
            with open(file_path, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Year", "Month", "Day", "Hour", "Minute", "Second", "Temperature", "Humidity"])

        with open(file_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(entries)


def load_existing_dates():
    """Ładuje daty, dla których dane już istnieją."""
    existing_files = [f for f in os.listdir(os.getcwd()) if f.startswith("data_") and f.endswith(".csv")]
    return [f.split("_")[1].split(".")[0] for f in existing_files]

def resample_data(data, interval):
    """Próbkuje dane w podanym interwale czasowym."""
    if 'Timestamp' not in data.columns:
        data['Timestamp'] = pd.to_datetime(data[['Year', 'Month', 'Day', 'Hour', 'Minute', 'Second']])
    data.set_index('Timestamp', inplace=True)
    resampled = data.resample(interval.lower()).mean()
    return resampled.reset_index()

def plot_data(time_period, frame):
    """Wyświetla dane w postaci wykresu punktowego dla wybranego okresu czasu."""
    try:
        all_data = []
        for file in os.listdir(os.getcwd()):
            if file.startswith("data_") and file.endswith(".csv"):
                file_date = file.split("_")[1].split(".")[0]
                if time_period == "Dzień" and file_date == datetime.now().strftime("%Y-%m-%d"):
                    data = pd.read_csv(file)
                    all_data.append(data)
                elif time_period == "Tydzień" and datetime.strptime(file_date, "%Y-%m-%d") >= datetime.now() - pd.Timedelta(days=7):
                    data = pd.read_csv(file)
                    all_data.append(data)
                elif time_period == "Miesiąc" and datetime.strptime(file_date, "%Y-%m-%d") >= datetime.now() - pd.Timedelta(days=30):
                    data = pd.read_csv(file)
                    all_data.append(data)
                elif time_period == "Rok" and datetime.strptime(file_date, "%Y-%m-%d") >= datetime.now() - pd.Timedelta(days=365):
                    data = pd.read_csv(file)
                    all_data.append(data)

        if all_data:
            full_data = pd.concat(all_data)
            full_data['Timestamp'] = pd.to_datetime(full_data[['Year', 'Month', 'Day', 'Hour', 'Minute', 'Second']])
            full_data = full_data.sort_values(by='Timestamp')  # Sortowanie danych po czasie

            # Ustawienia zakresów czasowych
            now = datetime.now()
            if time_period == "Dzień":
                start_time = datetime(now.year, now.month, now.day)
                end_time = start_time + pd.Timedelta(days=1)
            elif time_period == "Tydzień":
                start_time = now - pd.Timedelta(days=7)
                end_time = now
            elif time_period == "Miesiąc":
                start_time = now - pd.Timedelta(days=30)
                end_time = now
            elif time_period == "Rok":
                start_time = now - pd.Timedelta(days=365)
                end_time = now

            # Próbkowanie danych (dla tygodnia, miesiąca, roku)
            if time_period in ["Tydzień", "Miesiąc", "Rok"]:
                full_data = resample_data(full_data, '1h')  # Próbkowanie co godzinę

            # Tworzenie wykresu
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(full_data['Timestamp'], full_data['Temperature'], label='Temperatura', alpha=0.7, s=10)
            ax.scatter(full_data['Timestamp'], full_data['Humidity'], label='Wilgotność', alpha=0.7, s=10)
            ax.set_xlabel('Czas')
            ax.set_ylabel('Wartości')
            ax.set_title(f"Dane dla okresu: {time_period}")
            ax.legend()
            ax.grid(True)
            fig.autofmt_xdate()

            # Ustawienie zakresu osi X na podstawie okresu czasu
            ax.set_xlim(start_time, end_time)

            for widget in frame.winfo_children():
                widget.destroy()

            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack()
        else:
            messagebox.showinfo("Informacja", "Brak dostępnych danych dla wybranego okresu czasu.")
    except Exception as e:
        messagebox.showerror("Błąd", f"Błąd podczas wyświetlania wykresu: {e}")

def main_ui():
    """Główna funkcja interfejsu użytkownika."""
    def fetch_and_save_data():
        port = port_selection.get()
        if not port:
            messagebox.showerror("Błąd", "Proszę wybrać port USB.")
            return

        received_data = fetch_data_from_arduino(port)
        if received_data:
            save_data_to_csv(received_data)
            messagebox.showinfo("Sukces", "Dane zostały pobrane i zapisane.")

    root = tk.Tk()
    root.title("Arduino Logger Danych")

    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    ttk.Label(frame, text="Wybierz port USB:").grid(row=0, column=0, sticky=tk.W)

    ports = list_ports()
    port_selection = ttk.Combobox(frame, values=ports)
    port_selection.grid(row=0, column=1, sticky=(tk.W, tk.E))

    ttk.Button(frame, text="Pobierz dane", command=fetch_and_save_data).grid(row=1, column=0, columnspan=2, pady=10)

    ttk.Label(frame, text="Wyświetl dane dla:").grid(row=2, column=0, sticky=tk.W)

    time_period = ttk.Combobox(frame, values=["Dzień", "Tydzień", "Miesiąc", "Rok"])
    time_period.grid(row=2, column=1, sticky=(tk.W, tk.E))

    plot_frame = ttk.Frame(root, padding="10")
    plot_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def show_plot():
        selected_period = time_period.get()
        if selected_period:
            plot_data(selected_period, plot_frame)
        else:
            messagebox.showerror("Błąd", "Proszę wybrać okres czasu.")

    ttk.Button(frame, text="Pokaż wykres", command=show_plot).grid(row=3, column=0, columnspan=2, pady=10)

    root.mainloop()

if __name__ == "__main__":
    main_ui()
