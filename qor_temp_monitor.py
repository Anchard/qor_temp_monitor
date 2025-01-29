import tkinter as tk
from tkinter import ttk
import requests
import sqlite3
from email.mime.text import MIMEText
import smtplib
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

# Configurações
TARGET_URL = "http://192.168.3.203"
CHECK_INTERVAL = 1  # Segundos
ALERT_TEMP = 50  # Temperatura limite para alerta
EMAIL_RECIPIENT = "contato.tecnica.epc@mailo.com"
EMAIL_SENDER = "contato.tecnica.epc@mailo.com"
EMAIL_PASSWORD = "Tecnica@123"

# Banco de dados
conn = sqlite3.connect("temperaturas.db")
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS temperatura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        hora TEXT,
        cpu_temp REAL,
        dsp_temp REAL,
        codecs_temp REAL
    )
""")
conn.commit()

def get_qor_status():
    try:
        response = requests.get(TARGET_URL, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        def extract_temp(label):
            temp_element = soup.find(string=label)
            if temp_element:
                temp_value = temp_element.find_next().text.strip().replace("°C", "").replace("+", "")
                return float(temp_value)
            return None

        return extract_temp("CPU temp:"), extract_temp("DSP temp:"), extract_temp("Codecs temp:")
    except Exception:
        return None, None, None

def save_temperature(cpu_temp, dsp_temp, codecs_temp):
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    hora_atual = datetime.now().strftime("%H:%M:%S")
    c.execute("""
        INSERT INTO temperatura (data, hora, cpu_temp, dsp_temp, codecs_temp)
        VALUES (?, ?, ?, ?, ?)
    """, (data_hoje, hora_atual, cpu_temp, dsp_temp, codecs_temp))
    conn.commit()

# Configurações iniciais
last_email_sent = None  # Variável para armazenar a hora do último envio de e-mail

def send_email(cpu_temp, dsp_temp, codecs_temp):
    global last_email_sent  # Usar a variável global para controlar o envio de e-mails

    # Definir o intervalo mínimo entre os e-mails (por exemplo, 12 horas)
    email_interval = 12 * 60 * 60  # 12 horas em segundos
    current_time = datetime.now()

    # Verificar se já passou o intervalo mínimo desde o último envio
    if last_email_sent is None or (current_time - last_email_sent).total_seconds() >= email_interval:
        try:
            msg_content = f"""
            ALERTA: Uma das temperaturas do QOR ultrapassou {ALERT_TEMP}°C.
            Temperaturas registradas:
            - CPU: {cpu_temp}°C
            - DSP: {dsp_temp}°C
            - Codecs: {codecs_temp}°C
            Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            msg = MIMEText(msg_content)
            msg["Subject"] = "ALERTA DE TEMPERATURA - QOR"
            msg["From"] = EMAIL_SENDER
            msg["To"] = EMAIL_RECIPIENT

            with smtplib.SMTP("mail.mailo.com", 587) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())

            print("Email de alerta enviado!")
            last_email_sent = current_time  # Atualizar a hora do último envio
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
    else:
        print("O e-mail já foi enviado recentemente, aguardando próximo intervalo.")

class TempMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Monitor de Temperaturas - QOR")
        self.geometry("800x600")
        
        self.cpu_label = ttk.Label(self, text="CPU Temp: -- °C", font=("Arial", 12))
        self.cpu_label.pack()
        self.dsp_label = ttk.Label(self, text="DSP Temp: -- °C", font=("Arial", 12))
        self.dsp_label.pack()
        self.codecs_label = ttk.Label(self, text="Codecs Temp: -- °C", font=("Arial", 12))
        self.codecs_label.pack()

        self.fig, self.ax = plt.subplots()
        self.ax.set_title("Temperaturas ao Longo do Tempo")
        self.ax.set_xlabel("Tempo")
        self.ax.set_ylabel("Temperatura (°C)")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        self.cpu_line, = self.ax.plot([], [], "r-", label="CPU Temp")
        self.dsp_line, = self.ax.plot([], [], "b-", label="DSP Temp")
        self.codecs_line, = self.ax.plot([], [], "g-", label="Codecs Temp")
        
        self.ax.legend()
        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.get_tk_widget().pack()
        
        self.time_data = []
        self.cpu_data = []
        self.dsp_data = []
        self.codecs_data = []
        
        self.update_temperature_data()
    
    def update_temperature_data(self):
        cpu_temp, dsp_temp, codecs_temp = get_qor_status()
        if cpu_temp is not None and dsp_temp is not None and codecs_temp is not None:
            self.cpu_label.config(text=f"CPU Temp: {cpu_temp} °C")
            self.dsp_label.config(text=f"DSP Temp: {dsp_temp} °C")
            self.codecs_label.config(text=f"Codecs Temp: {codecs_temp} °C")
            save_temperature(cpu_temp, dsp_temp, codecs_temp)

            if cpu_temp > ALERT_TEMP or dsp_temp > ALERT_TEMP or codecs_temp > ALERT_TEMP:
                send_email(cpu_temp, dsp_temp, codecs_temp)
            
            current_time = datetime.now()
            self.time_data.append(current_time)
            self.cpu_data.append(cpu_temp)
            self.dsp_data.append(dsp_temp)
            self.codecs_data.append(codecs_temp)
            
            if len(self.time_data) > 20:
                self.time_data.pop(0)
                self.cpu_data.pop(0)
                self.dsp_data.pop(0)
                self.codecs_data.pop(0)
            
            self.cpu_line.set_data(self.time_data, self.cpu_data)
            self.dsp_line.set_data(self.time_data, self.dsp_data)
            self.codecs_line.set_data(self.time_data, self.codecs_data)
            
            self.ax.set_xlim(self.time_data[0], self.time_data[-1])
            self.ax.set_ylim(min(min(self.cpu_data, self.dsp_data, self.codecs_data)) - 5,
                             max(max(self.cpu_data, self.dsp_data, self.codecs_data)) + 5)
            self.ax.figure.autofmt_xdate()
            self.canvas.draw()
        
        self.after(CHECK_INTERVAL * 1000, self.update_temperature_data)

if __name__ == "__main__":
    app = TempMonitorApp()
    app.mainloop()