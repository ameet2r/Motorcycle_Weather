import pandas as pd
import numpy as np

def generate_expert_synthetic_data(samples=15000):
    np.random.seed(42)
    
    # Raw Data Generation
    data = {
        'temp': np.random.uniform(10, 115, samples),
        'wind_speed': np.random.uniform(0, 50, samples),
        'precip_prob': np.random.uniform(0, 100, samples),
        'visibility': np.random.uniform(0, 10, samples),
        'humidity': np.random.uniform(5, 95, samples),
        'is_day': np.random.choice([0, 1], samples),
    }
    df = pd.DataFrame(data)
    
    # Derived Features
    df['wind_gust'] = df['wind_speed'] + np.random.exponential(8, samples)
    df['gust_delta'] = df['wind_gust'] - df['wind_speed']
    # Simplified Apparent Temp (Wind Chill/Heat Index simulation)
    df['apparent_temp'] = df['temp'] - (df['wind_speed'] * 0.4) + (df['humidity'] * 0.1)

    def calculate_expert_score(row):
        score = 100.0
        
        # --- 1. CHECK DEAL-BREAKERS (The "Clamp") ---
        if (row['apparent_temp'] <= 32 or 
            row['apparent_temp'] >= 105 or 
            row['wind_speed'] >= 40 or 
            row['wind_gust'] >= 55 or 
            row['visibility'] < 0.5):
            return np.random.uniform(0, 10) # Danger Zone

        # --- 2. TEMPERATURE LOGIC (Non-Linear) ---
        t = row['apparent_temp']
        if 60 <= t <= 80: pass # Ideal
        elif 50 <= t < 60: score *= 0.9
        elif 40 <= t < 50: score *= 0.7
        elif 81 <= t < 95: score *= 0.85
        elif 95 <= t < 105: score *= 0.6

        # --- 3. WIND LOGIC (Gust Delta Focus) ---
        if row['wind_speed'] > 15:
            score -= (row['wind_speed'] * 1.2)
        
        if row['gust_delta'] >= 25: score *= 0.3 # Major instability
        elif row['gust_delta'] >= 15: score *= 0.6

        # --- 4. PRECIPITATION & VISIBILITY ---
        # Probability scaling
        if row['precip_prob'] > 20:
            score -= (row['precip_prob'] * 0.5)
        
        # Visibility degradation
        if row['visibility'] < 5:
            score *= (row['visibility'] / 5) # Linear drop as visibility fades

        # --- 5. NIGHT PENALTY ---
        if row['is_day'] == 0:
            score *= 0.9 

        return max(0, min(100, score))

    df['ride_score'] = df.apply(calculate_expert_score, axis=1)
    return df

# Create the new "Smart" Dataset
df_expert = generate_expert_synthetic_data()
df_expert.to_csv('expert_motorcycle_data.csv', index=False)
