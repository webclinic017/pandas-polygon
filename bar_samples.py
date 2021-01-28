import pandas as pd
from bar_features import output_new_bar


def tick_rule(latest_price: float, prev_price: float, last_side: int=0) -> int:
    try:
        diff = latest_price - prev_price
    except:
        diff = None
    if diff > 0.0:
        side = 1
    elif diff < 0.0:
        side = -1
    elif diff == 0.0:
        side = last_side
    else:
        side = 0
    return side


def imbalance_runs(state: dict) -> dict:
    if len(state['trades']['side']) >= 2:
        if state['trades']['side'][-1] == state['trades']['side'][-2]:
            state['stat']['tick_run'] += 1        
            state['stat']['volume_run'] += state['trades']['volume'][-1]
            state['stat']['dollar_run'] += state['trades']['price'][-1] * state['trades']['volume'][-1]
        else:
            state['stat']['tick_run'] = 0
            state['stat']['volume_run'] = 0
            state['stat']['dollar_run'] = 0
    return state


def imbalance_net(state: dict) -> dict:
    state['stat']['tick_imbalance'] += state['trades']['side'][-1]
    state['stat']['volume_imbalance'] += (state['trades']['side'][-1] * state['trades']['volume'][-1])
    state['stat']['dollar_imbalance'] += (state['trades']['side'][-1] * state['trades']['volume'][-1] * state['trades']['price'][-1])
    return state


def reset_state(thresh: dict={}) -> dict:
    state = {}    
    state['thresh'] = thresh
    state['stat'] = {}
    # accumulators
    state['stat']['duration_sec'] = 0
    state['stat']['price_min'] = 10 ** 5
    state['stat']['price_max'] = 0
    state['stat']['price_range'] = 0
    state['stat']['price_return'] = 0
    state['stat']['jma_min'] = 10 ** 5
    state['stat']['jma_max'] = 0
    state['stat']['jma_range'] = 0
    state['stat']['jma_return'] = 0
    state['stat']['tick_count'] = 0
    state['stat']['volume'] = 0
    state['stat']['dollars'] = 0
    state['stat']['tick_imbalance'] = 0
    state['stat']['volume_imbalance'] = 0
    state['stat']['dollar_imbalance'] = 0
    # copy of tick events
    state['trades'] = {}
    state['trades']['date_time'] = []
    state['trades']['price'] = []
    state['trades']['volume'] = []
    state['trades']['side'] = []
    state['trades']['jma'] = []
    # trigger status
    state['trigger_yet?!'] = 'waiting'
    return state


def check_bar_thresholds(state: dict) -> dict:

    def get_next_renko_thresh(renko_size: float, last_bar_return: float, reversal_multiple: float) -> tuple:
        if last_bar_return >= 0:
            thresh_renko_bull = renko_size
            thresh_renko_bear = -renko_size * reversal_multiple
        elif last_bar_return < 0:
            thresh_renko_bull = renko_size * reversal_multiple
            thresh_renko_bear = -renko_size
        return thresh_renko_bull, thresh_renko_bear

    if 'renko_size' in state['thresh']:
        try:
            state['thresh']['renko_bull'], state['thresh']['renko_bear'] = get_next_renko_thresh(
                renko_size=state['thresh']['renko_size'],
                last_bar_return=state['stat']['last_bar_return'],
                reversal_multiple=state['thresh']['renko_reveral_multiple']
            )
        except:
            state['thresh']['renko_bull'] = state['thresh']['renko_size']
            state['thresh']['renko_bear'] = -state['thresh']['renko_size']

        if state['stat'][state['thresh']['renko_return']] >= state['thresh']['renko_bull']:
            state['trigger_yet?!'] = 'renko_up'
        if state['stat'][state['thresh']['renko_return']] < state['thresh']['renko_bear']:
            state['trigger_yet?!'] = 'renko_down'

    if 'max_duration_sec' in state['thresh'] and state['stat']['duration_sec'] > state['thresh']['max_duration_sec']:
        state['trigger_yet?!'] = 'duration'

    if 'volume_imbalance' in state['thresh'] and abs(state['stat']['volume_imbalance']) >= state['thresh']['volume_imbalance']:
        state['trigger_yet?!'] = 'volume_imbalance'

    # override newbar trigger with 'minimum' thresholds
    if 'min_duration_sec' in state['thresh'] and state['stat']['duration_sec'] < state['thresh']['min_duration_sec']:
        state['trigger_yet?!'] = 'waiting'

    if 'min_tick_count' in state['thresh'] and state['stat']['tick_count'] < state['thresh']['min_tick_count']:
        state['trigger_yet?!'] = 'waiting'

    if 'min_price_range' in state['thresh'] and state['stat']['price_range'] < state['thresh']['min_price_range']:
        state['trigger_yet?!'] = 'waiting'

    if 'min_jma_range' in state['thresh'] and state['stat']['jma_range'] < state['thresh']['min_jma_range']:
        state['trigger_yet?!'] = 'waiting'

    return state


def update_bar_state(tick: dict, state: dict, bars: list, thresh: dict={}) -> tuple:

    state['trades']['date_time'].append(tick['date_time'])
    state['trades']['price'].append(tick['price'])
    state['trades']['jma'].append(tick['jma'])
    state['trades']['volume'].append(tick['volume'])

    if len(state['trades']['price']) >= 2:
        tick_side = tick_rule(
            latest_price=state['trades']['price'][-1],
            prev_price=state['trades']['price'][-2],
            last_side=state['trades']['side'][-1]
            )
    else:
        tick_side = 0
    state['trades']['side'].append(tick_side)

    state = imbalance_net(state)
    # state = imbalance_runs(state)
    state['stat']['duration_sec'] = (tick['date_time'].value - state['trades']['date_time'][0].value) // 10**9
    state['stat']['tick_count'] += 1
    state['stat']['volume'] += tick['volume']
    state['stat']['dollars'] += tick['price'] * tick['volume']
    # price
    state['stat']['price_min'] = tick['price'] if tick['price'] < state['stat']['price_min'] else state['stat']['price_min']
    state['stat']['price_max'] = tick['price'] if tick['price'] > state['stat']['price_max'] else state['stat']['price_max']
    state['stat']['price_range'] = state['stat']['price_max'] - state['stat']['price_min']
    state['stat']['price_return'] = tick['price'] - state['trades']['price'][0]
    state['stat']['last_bar_return'] = bars[-1]['price_return'] if len(bars) > 0 else 0
    # jma
    state['stat']['jma_min'] = tick['jma'] if tick['jma'] < state['stat']['jma_min'] else state['stat']['jma_min']
    state['stat']['jma_max'] = tick['jma'] if tick['jma'] > state['stat']['jma_max'] else state['stat']['jma_max']
    state['stat']['jma_range'] = state['stat']['jma_max'] - state['stat']['jma_min']
    state['stat']['jma_return'] = tick['jma'] - state['trades']['jma'][0]
    # check state tirggered sample threshold
    state = check_bar_thresholds(state)
    if state['trigger_yet?!'] != 'waiting':
        new_bar = output_new_bar(state)
        bars.append(new_bar)
        state = reset_state(thresh)
    
    return bars, state


def filter_tick(tick: dict, state: list, jma_length: int=7, jma_power: float=2.0) -> tuple:
    from utils_filters import jma_filter_update

    jma_state = jma_filter_update(
        value=tick['price'],
        state=state[-1]['jma_state'],
        length=jma_length,
        power=jma_power,
        phase=0.0,
        )
    tick.update({ # add jma features to 'tick'
        'jma': jma_state['jma'],
        'pct_diff': (tick['price'] - jma_state['jma']) / jma_state['jma'],
        'jma_state': jma_state,
        })
    state.append(tick) # add new tick to buffer
    state = state[-100:] # keep most recent items

    tick['date_time'] = tick['sip_dt'].tz_localize('UTC').tz_convert('America/New_York')

    if tick['volume'] < 1:  # zero volume/size tick
        tick['status'] = 'zero_volume'
    elif len(state) <= (jma_length + 1):  # filling window/buffer
        tick['status'] = 'filter_warm_up'
    elif tick['irregular'] == True:  # 'irrgular' tick condition
        tick['status'] = 'irregular_condition'
    elif abs(tick['sip_dt'] - tick['exchange_dt']) > pd.to_timedelta(2, unit='S'): # remove large ts deltas
        tick['status'] = 'timestamps_delta'
    elif abs(tick['pct_diff']) > 0.002:  # jma filter outlier
        tick['status'] = 'outlier_filter'
    else:
        tick['status'] = 'clean'

    if tick['status'] not in ['clean', 'filter_warm_up']:
        state.pop(-1)

    tick.pop('sip_dt', None)
    tick.pop('exchange_dt', None)
    tick.pop('irregular', None)
    return tick, state


def build_bars(ticks_df: pd.DataFrame, thresh: dict) -> tuple:
    filter_state = [{'jma_state': {
        'e0': ticks_df.price.values[0],
        'e1': 0.0,
        'e2': 0.0,
        'jma': ticks_df.price.values[0],
        }}]
    bar_state = reset_state(thresh)
    bars = []
    ticks = []
    for t in ticks_df.itertuples():
        tick_raw = {
            'sip_dt': t.sip_dt,
            'exchange_dt': t.exchange_dt,
            'price': t.price,
            'volume': t.size,
            'irregular': t.irregular,
            'status': 'new',
        }
        tick_filtered, filter_state = filter_tick(tick_raw, filter_state)
        
        if tick_filtered['status'] == 'clean':
            bars, bar_state = update_bar_state(tick_filtered, bar_state, bars, thresh)

        ticks.append(tick_filtered)

    return bars, ticks
