import pandas as pd
import json
import plotly.express as px
from datetime import datetime, timedelta

def load_config(file_path='config.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_schedule(order_plan, config, deadline_str="03:00"):
    products = config['products']
    # Дедлайн: 03:00 завтрашнього дня
    target_date = datetime.now() + timedelta(days=1)
    deadline = target_date.replace(hour=int(deadline_str[:2]), minute=int(deadline_str[3:]), second=0, microsecond=0)
    
    schedule_data = []
    
    # Відстежуємо вільний час на лініях (рахуємо НАЗАД від дедлайну)
    # line_available_at зберігає час, коли лінія має БУТИ ВІЛЬНОЮ, щоб встигнути до дедлайну
    line_available_at = {1: deadline, 2: deadline}

    # Сортуємо замовлення за пріоритетом (найдовші процеси пакування першими)
    # Житній та Батон мають низьку швидкість пакування, тому вони критичні
    for item in sorted(order_plan, key=lambda x: products[x['name']]['pack_rate']):
        name = item['name']
        qty = item['qty']
        spec = products[name]
        line_num = spec['line']
        
        units_per_chan = int(spec['weight_batch'] / spec['weight_unit'])
        num_batches = (qty // units_per_chan) + (1 if qty % units_per_chan > 0 else 0)
        
        # Час тех. циклу ПІСЛЯ лінії (ферментація + випікання + охолодження)
        post_line_fixed = spec['proof_time'] + spec['bake_time'] + spec['cool_time']
        # Час пакування однієї діжі
        pack_duration = units_per_chan / spec['pack_rate']

        # Рахуємо кожну діжу цього продукту (від останньої до першої)
        for b in range(num_batches, 0, -1):
            
            # Ця діжа має ПОВНІСТЮ закінчити пакування до line_available_at[line_num]
            finish_packing = line_available_at[line_num]
            
            # Початок пакування цієї діжі
            start_packing = finish_packing - timedelta(minutes=pack_duration)
            
            # Щоб почати пакувати вчасно, вона має вийти з лінії формування за (fixed_delay) хвилин до цього
            end_form = start_packing - timedelta(minutes=post_line_fixed)
            
            # Самі процеси на лінії (формування)
            start_form = end_form - timedelta(minutes=spec['form_time'])
            
            # Готовність тіста (бродіння має закінчитись до початку формування)
            ready_dough = start_form
            
            # Старт замісу опари/закваски
            start_mix = ready_dough - timedelta(minutes=spec['mix_time'])
            
            # Оновлюємо поріг для наступної (попередньої в часі) діжі на цій лінії
            # Наступна діжа має звільнити лінію до того, як ця її займе
            line_available_at[line_num] = start_form
            
            schedule_data.append({
                "Продукт": name,
                "Завдання": f"{name} (Чан {b})",
                "Лінія": f"Лінія {line_num}",
                "Старт замісу (Оператор)": start_mix,
                "Готовність тіста": ready_dough,
                "Початок формування": start_form,
                "Кінець формування": end_form,
                "Вихід з печі/Охолодження": end_form + timedelta(minutes=spec['proof_time'] + spec['bake_time']),
                "Фініш пакування (Дедлайн)": finish_packing
            })

    return pd.DataFrame(schedule_data)

# --- ВХІДНІ ДАНІ ДЛЯ РОЗРАХУНКУ ---
current_order = [
    {"name": "Хліб Житній", "qty": 3000},
    {"name": "Батон", "qty": 4000},
    {"name": "Булка здобна", "qty": 10000}
]

try:
    config = load_config()
    df = calculate_schedule(current_order, config)

    # Сортуємо результат по черговості робіт для оператора
    df = df.sort_values('Старт замісу (Оператор)')

    # 1. Збереження в Excel
    file_excel = "Schedule_Plan.xlsx"
    df.to_excel(file_excel, index=False)

    # 2. Створення інтерактивного графіка Ганта
    # Відображаємо цикл від замісу до пакування
    fig = px.timeline(df, 
                      x_start="Старт замісу (Оператор)", 
                      x_end="Фініш пакування (Дедлайн)", 
                      y="Лінія", 
                      color="Продукт",
                      hover_data=["Завдання", "Початок формування"],
                      title="Оптимізований графік виробництва (Дедлайн 03:00)")
    
    fig.update_yaxes(autorange="reversed")
    fig.write_html("gantt_chart.html")

    print("--- РОЗРАХУНОК ЗАВЕРШЕНО ---")
    print(f"Файли '{file_excel}' та 'gantt_chart.html' оновлено.")
    print(f"Найраніший початок роботи (точка старт): {df['Старт замісу (Оператор)'].min().strftime('%H:%M (%d.%m)')}")

except Exception as e:
    print(f"Помилка: {e}")
