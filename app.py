from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import os

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

    order = ['N330QT', 'N331QT', 'N332QT', 'N334QT', 'N335QT', 'N336QT', 'N337QT']
    df['aeronave'] = pd.Categorical(df['Reg.'], categories=order, ordered=True)
    df = df.sort_values('aeronave', ascending=False)
    fig, ax = plt.subplots(figsize=(8.5, 11))  # Tamaño carta

    for i, aeronave in enumerate(reversed(order)):
        vuelos_aeronave = df[df['aeronave'] == aeronave]
        for _, vuelo in vuelos_aeronave.iterrows():
            start = vuelo['fecha_salida']
            duration = vuelo['fecha_llegada'] - vuelo['fecha_salida']
            rect_height = 0.2
            ax.broken_barh([(start, duration)], (i - rect_height/2, rect_height), facecolors='#ADD8E6')  # Azul claro
            flight_text = vuelo['Flight']
            trip_text = vuelo['Trip']
            notas_text = vuelo['Notas']
            tripadi_text = vuelo['Tripadi']
            
            if text_fits(ax, flight_text, start, duration):
                ax.text(start + duration / 2, i, flight_text, ha='center', va='center', color='black', fontsize=8)
            else:
                ax.text(start + duration / 2, i - rect_height, flight_text, ha='center', va='top', color='black', fontsize=8)
            
            # Trip text above the bar, slightly higher
            ax.text(start + duration / 2, i + 0.35, trip_text, ha='center', va='bottom', color='blue', fontsize=8)
            
            # Notas text below the bar
            ax.text(start + duration / 2, i - 0.25, notas_text, ha='center', va='top', color='green', fontsize=8)
            
            # Tripadi text below the Notas
            ax.text(start + duration / 2, i - 0.45, tripadi_text, ha='center', va='top', color='purple', fontsize=8)

            origin_text = vuelo['From']
            if text_fits(ax, origin_text, start, duration):
                ax.text(start, i + 0.2, origin_text, ha='left', va='center', color='black', fontsize=8)
            else:
                ax.text(start, i - rect_height, origin_text, ha='left', va='top', color='black', fontsize=8)
            destination_text = vuelo['To']
            if text_fits(ax, destination_text, start, duration):
                ax.text(start + duration, i + 0.2, destination_text, ha='right', va='center', color='black', fontsize=8)
            else:
                ax.text(start + duration, i - rect_height, destination_text, ha='right', va='top', color='black', fontsize=8)
            ax.text(start, i - 0.2, vuelo['fecha_salida'].strftime('%H:%M'), ha='left', va='center', color='black', fontsize=6)
            ax.text(start + duration, i - 0.2, vuelo['fecha_llegada'].strftime('%H:%M'), ha='right', va='center', color='black', fontsize=6)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(reversed(order))
    ax.set_ylim(-1, len(order))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45, fontsize=10)
    
    start_day = df['fecha_salida'].min().normalize() + pd.Timedelta(hours=5)
    end_day = (start_day + pd.Timedelta(days=1)) - pd.Timedelta(minutes=1)
    ax.set_xlim(start_day, end_day)
    
    plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.15)
    plt.xlabel('Hora')
    plt.ylabel('Aeronave')
    plt.title(f'Programación de Vuelos QT {additional_text}')

    buf = io.BytesIO()
    plt.savefig(buf, format='pdf', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        table_data = request.form['table_data']
        additional_text = request.form.get('additional_text')
        try:
            df = pd.read_json(table_data)
        except ValueError as e:
            return jsonify({'error': f"JSON parsing error: {e}"}), 400

        pdf, error = process_and_plot(df, additional_text)
        if error:
            return jsonify({'error': error}), 400
        return send_file(pdf, as_attachment=True, download_name='programacion_vuelos_qt.pdf', mimetype='application/pdf')
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
