from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import os
from PyPDF2 import PdfMerger

app = Flask(__name__)

def parse_dates(date_series):
    formats = ['%d/%m/%Y %H:%M', '%d%b %H:%M']
    for fmt in formats:
        try:
            return pd.to_datetime(date_series, format=fmt, dayfirst=True)
        except (ValueError, TypeError):
            continue
    raise ValueError("Date conversion error: None of the formats matched.")

def text_fits(ax, text, start, duration):
    text_length_approx = len(text) * 0.02
    return duration.total_seconds() / 3600 >= text_length_approx

def draw_text(ax, text, x, y, duration, align='center', **kwargs):
    max_width = duration.total_seconds() / 3600 * 0.8  # Limitar el ancho del texto a 80% de la duración
    if text_fits(ax, text, x, duration):
        ax.text(x + duration / 2, y, text, ha=align, va='center', **kwargs)
    else:
        truncated_text = text[:int(max_width * 50)] + '...'  # Ajustar longitud del texto basado en duración
        ax.text(x + duration / 2, y, truncated_text, ha=align, va='center', **kwargs)

def generate_plot(df, additional_text, start_time, end_time):
    order = ['N330QT', 'N331QT', 'N332QT', 'N334QT', 'N335QT', 'N336QT', 'N337QT']
    df['aeronave'] = pd.Categorical(df['Reg.'], categories=order, ordered=True)
    df = df.sort_values('aeronave', ascending=False)
    fig, ax = plt.subplots(figsize=(11, 8.5))  # Tamaño carta horizontal

    for i, aeronave in enumerate(reversed(order)):
        vuelos_aeronave = df[df['aeronave'] == aeronave]
        for _, vuelo in vuelos_aeronave.iterrows():
            start = vuelo['fecha_salida']
            duration = vuelo['fecha_llegada'] - vuelo['fecha_salida']
            if start < start_time:
                duration -= (start_time - start)
                start = start_time
            if start + duration > end_time:
                duration = end_time - start
            rect_height = 0.2
            ax.broken_barh([(start, duration)], (i - rect_height/2, rect_height), facecolors='#ADD8E6')  # Azul claro
            
            draw_text(ax, vuelo['Flight'], start, i, duration, color='black', fontsize=8)
            draw_text(ax, vuelo['Trip'], start, i + 0.3, duration, color='blue', fontsize=8)  # Bajado ligeramente
            draw_text(ax, vuelo['Notas'], start, i - 0.25, duration, color='green', fontsize=8)
            draw_text(ax, vuelo['Tripadi'], start, i - 0.4, duration, color='purple', fontsize=8)  # Subido ligeramente

            if text_fits(ax, vuelo['From'], start, duration):
                ax.text(start, i + 0.2, vuelo['From'], ha='left', va='center', color='black', fontsize=8)
            if text_fits(ax, vuelo['To'], start, duration):
                ax.text(start + duration, i + 0.2, vuelo['To'], ha='right', va='center', color='black', fontsize=8)
            
            ax.text(start, i - 0.2, vuelo['fecha_salida'].strftime('%H:%M'), ha='left', va='center', color='black', fontsize=6)
            ax.text(start + duration, i - 0.2, vuelo['fecha_llegada'].strftime('%H:%M'), ha='right', va='center', color='black', fontsize=6)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(reversed(order))
    ax.set_ylim(-1, len(order))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45, fontsize=10)
    
    ax.set_xlim(start_time, end_time)
    
    plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.15)
    plt.xlabel('Hora')
    plt.ylabel('Aeronave')
    plt.title(f'Programación de Vuelos QT {additional_text}')

    buf = io.BytesIO()
    plt.savefig(buf, format='pdf', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def process_and_plot(df, additional_text):
    try:
        df['fecha_salida'] = parse_dates(df['STD'])
        df['fecha_llegada'] = parse_dates(df['STA'])
    except KeyError as e:
        return None, f"Missing column in input data: {e}"
    except ValueError as e:
        return None, f"Date conversion error: {e}"

    df['Trip'] = df['Trip'].fillna(' ')
    df['Notas'] = df['Notas'].fillna(' ')
    df['Tripadi'] = df['Tripadi'].fillna(' ')

    pdf_buffers = []
    current_date = df['fecha_salida'].min().normalize()
    end_of_data = df['fecha_llegada'].max()

    while current_date <= end_of_data:
        current_start_time = current_date + pd.Timedelta(hours=5)
        current_end_time = current_start_time + pd.Timedelta(hours=27) - pd.Timedelta(minutes=1)
        df_period = df[(df['fecha_salida'] >= current_start_time) & (df['fecha_salida'] < current_end_time)]
        if not df_period.empty:
            buf = generate_plot(df_period, additional_text, current_start_time, current_end_time)
            pdf_buffers.append(buf)
        current_date += pd.Timedelta(days=1)

    return pdf_buffers, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        table_data = request.form['table_data']
        additional_text = request.form.get('additional_text')
        try:
            df = pd.read_json(table_data)
        except ValueError as e:
            return jsonify({'error': f"JSON parsing error: {e}"}), 400

        pdf_buffers, error = process_and_plot(df, additional_text)
        if error:
            return jsonify({'error': error}), 400
        
        output = io.BytesIO()
        merger = PdfMerger()
        for buf in pdf_buffers:
            merger.append(buf)
        merger.write(output)
        merger.close()
        output.seek(0)
        
        return send_file(output, as_attachment=True, download_name='programacion_vuelos_qt.pdf', mimetype='application/pdf')
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

