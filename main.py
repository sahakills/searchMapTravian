import json
import pandas as pd
import html
import re
import os
from datetime import datetime

# === Подготовка ===
now = datetime.now()
timestamp = now.strftime('%Y%m%d_%H%M%S')
player_stats_file = f'player_stats_{timestamp}.csv'

# === Регулярки ===
player_re = re.compile(r'{k.spieler} (.+?)<br')
pop_re = re.compile(r'{k.einwohner} (\d+)')
bracket_tag_re = re.compile(r'{[ka]\.[^}]+}')

# === Чтение JSON карты ===
with open('travian_map.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

parsed_tiles = []

for tile in data['tiles']:
    x = tile['position']['x']
    y = tile['position']['y']
    title = bracket_tag_re.sub('', html.unescape(tile.get('title', ''))).strip()
    text = html.unescape(tile.get('text', ''))
    uid = tile.get('uid')
    did = tile.get('did')

    player = None
    population = None

    if player_match := player_re.search(text):
        player = player_match.group(1)
    if pop_match := pop_re.search(text):
        population = int(pop_match.group(1))

    parsed_tiles.append({
        'x': x,
        'y': y,
        'player': player,
        'population': population,
        'uid': uid,
        'did': did
    })

# === DataFrame по деревням ===
df_villages = pd.DataFrame(parsed_tiles)
df_villages = df_villages.dropna(subset=['did', 'player', 'population'])
df_villages['did'] = df_villages['did'].astype(int)

# === Сводка по игрокам ===
df_players = df_villages.groupby('player', as_index=False)['population'].sum()
df_players['timestamp'] = timestamp

# Сохраняем снимок
df_players.to_csv(player_stats_file, index=False)
print(f"✅ Сохранена сводка по игрокам: {player_stats_file}")

# === Работа с историей ===
# Собираем все старые player_stats_*.csv
player_stat_files = sorted(f for f in os.listdir('.') if f.startswith('player_stats_') and f.endswith('.csv'))

# Собираем историю в один DataFrame
history = pd.DataFrame()

for file in player_stat_files:
    df = pd.read_csv(file)
    history = pd.concat([history, df], ignore_index=True)

# === Подсчёт неактивности ===
inactive_players = []

for player in history['player'].unique():
    player_data = history[history['player'] == player].sort_values('timestamp')

    # сравниваем население по дням
    prev_pop = None
    inactive_days = 0
    last_active_date = None

    for _, row in player_data.iterrows():
        current_pop = row['population']
        ts = row['timestamp']

        if prev_pop is not None:
            if current_pop > prev_pop:
                inactive_days = 0
                last_active_date = ts
            else:
                inactive_days += 1
        else:
            last_active_date = ts

        prev_pop = current_pop

    if inactive_days >= 2:
        inactive_players.append({
            'player': player,
            'inactive_days': inactive_days,
            'last_active': last_active_date
        })

# === Сохраняем список неактивных игроков ===
df_inactive = pd.DataFrame(inactive_players)
if not df_inactive.empty:
    df_inactive = df_inactive.sort_values(by='inactive_days', ascending=False)
    df_inactive.to_csv('inactive_players.csv', index=False)
    print("📉 Обновлён список неактивных игроков: inactive_players.csv")
    print(df_inactive.head(10))
else:
    print("✅ Пока нет неактивных игроков (2+ дня без роста).")
