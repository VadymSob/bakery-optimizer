import pandas as pd
import json
import plotly.express as px
from datetime import datetime, timedelta

def load_config(file_path='config.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_schedule(order_plan, config, deadline_str="03:00"):
    products = config['products']
    # Встановлюємо дедлайн на завтрашнє число
    deadline = datetime.now().replace(hour=int(deadline_str[:2]), minute=int(deadline_str[3:]), second=0, microsecond=0) + timedelta(days=1)
    
    schedule_data = []
    # Стан ліній (час, коли лінія звільняється для наступної діжі при русі НАЗАД)
    line_busy_until = {1: deadline, 2: deadline}

    # Обробляємо замовлення
    for item in order_plan:
        name = item['name']
        qty = item['qty']
        spec = products[name]
        
        units_per_chan = int(spec['weight_batch'] / spec['weight_unit'])
        num_batches = (qty // units_per_chan) + (1 if qty % units_per_chan > 0 else 0)
        
        # Рахуємо кожну діжу окремо (від останньої до першої)
        for b in range(num_batches, 0, -1):
            line_num = spec['line']
            
            # Розрахунок тех. циклу ПІСЛЯ формування (хв)
            # Ферментація + Випікання + Охолодження + Час на пакування всієї діжі
            pack_duration = units_per_chan / spec['pack_rate']
            post_form_time = spec['proof_time'] + spec['bake_time'] + spec['cool_time'] + pack_duration
            
            # Час КІНЦЯ формування на лінії
            end_form = line_busy_until[line_num] - timedelta(minutes=0) # Можна додати тех.паузу між чанами
            start_form = end_form - timedelta(minutes=spec['form_time'])
            
            # Час бродіння (готове тісто має бути до початку формування)
            ready_dough = start_form
            start_mix = ready_dough - timedelta(minutes=spec['mix_time'])
            
            # Час завершення пакування (для графіка)
            finish_all = end_form + timedelta(minutes=post_form_time)
            
            # Оновлюємо "хвіст" лінії для наступного (попереднього у часі) чану
            line_busy_until[line_num] = start_form
            
            schedule_data.append({
                "Task": f"{name} (Чан {b})",
                "Start": start_mix,
                "Finish": finish_all,
                "Mix_Start": start_mix,
                "Form_Start": start_form,
                "Form_End": end_form,
                "Line": f"Лінія {line_num}",
                "Product": name
            })

    return pd.DataFrame(schedule_data)

# --- ЗАМОВЛЕННЯ НА ЗМІНУ ---
current_order = [
    {"name": "Хліб Житній", "qty": 3000},
    {"name": "Батон", "qty": 4000},
    {"name": "Булка здобна", "qty": 10000}
]

# Запуск логіки
config = load_config()
df = calculate_schedule(current_order, config)

# 1. Зберігаємо в Excel
excel_df = df[['Product', 'Task', 'Line', 'Mix_Start', 'Form_Start', 'Finish']].sort_values('Mix_Start')
excel_df.to_excel("Schedule_Plan.xlsx", index=False)

# 2. Створюємо графік Ганта
fig = px.timeline(df, x_start="Start", x_end="Finish", y="Line", color="Product", 
                  hover_data=["Task", "Form_Start"], title="Графік завантаження ліній виробництва")
fig.update_yaxes(autorange="reversed")
fig.write_html("gantt_chart.html")

print("Готово! Перевірте файли Schedule_Plan.xlsx та gantt_chart.html")
