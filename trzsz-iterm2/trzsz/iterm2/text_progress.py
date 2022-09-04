# MIT License
#
# Copyright (c) 2022 Lonny Wong
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
from trzsz.libs.utils import TrzszCallback

def display_length(s):
    l = 0
    for c in s:
        l += 1 if len(c.encode('utf8')) == 1 else 2
    return l

def ellipsis_string(s, m):
    m -= 3
    l = 0
    r = []
    for c in s:
        if len(c.encode('utf8')) > 1:
            if l + 2 > m:
                break
            l += 2
        else:
            if l + 1 > m:
                break
            l += 1
        r.append(c)
    r.append('...')
    return ''.join(r), l + 3

def size_to_str(size):
    if size < 0:
        return 'NaN'
    unit = 'B'
    while True:
        if size < 1024:
            break
        size = size / 1024
        unit = 'KB'
        if size < 1024:
            break
        size = size / 1024
        unit = 'MB'
        if size < 1024:
            break
        size = size / 1024
        unit = 'GB'
        if size < 1024:
            break
        size = size / 1024
        unit = 'TB'
        break
    if size >= 100:
        return f'{size:.0f}{unit}'
    if size >= 10:
        return f'{size:.1f}{unit}'
    return f'{size:.2f}{unit}'

def time_to_str(seconds):
    if seconds < 0:
        return 'NaN'
    result = ''
    if seconds >= 3600:
        result += str(int(seconds / 3600)) + ':'
        seconds %= 3600
    minute = int(seconds / 60)
    result += (str(minute) if minute >= 10 else ('0' + str(minute))) + ':'
    second = round(seconds % 60)
    result += str(second) if second >= 10 else ('0' + str(second))
    return result

SPEED_ARRAY_SIZE = 10

class TextProgressBar(TrzszCallback):
    def __init__(self, loop, session, tmux_pane_width=None):
        self.num = 0
        self.idx = 0
        self.name = ''
        self.size = 0
        self.step = 0
        self.start_time = 0
        self.update_time = 0
        self.first_write = True
        self.speed_cnt = 0
        self.speed_idx = 0
        self.time_array = [0] * SPEED_ARRAY_SIZE
        self.step_array = [0] * SPEED_ARRAY_SIZE
        self.loop = loop
        self.session = session
        self.tmux_pane_width = tmux_pane_width or -1
        self.columns = self.tmux_pane_width if self.tmux_pane_width > 0 else session.grid_size.width

    def on_num(self, num):
        self.num = num

    def on_name(self, name):
        self.name = name
        self.idx += 1
        self.start_time = time.time()
        self.time_array[0] = self.start_time
        self.step_array[0] = 0
        self.speed_cnt = 1
        self.speed_idx = 1

    def on_size(self, size):
        self.size = size

    def on_step(self, step):
        self.step = step
        self._show_progress()

    def on_done(self):
        if not self.first_write:
            if self.tmux_pane_width > 0:
                self._inject_to_iterm2(f'\x1b[{self.columns}D')
            else:
                self._inject_to_iterm2('\r')
            self.first_write = True

    def _show_progress(self):
        now = time.time()
        if now - self.update_time < 0.5:
            return
        self.update_time = now

        if self.size == 0:
            return
        percentage = str(round(self.step * 100 / self.size)) + '%'
        total = size_to_str(self.step)
        speed = self._get_speed(now)
        speed_str = size_to_str(speed) + '/s'
        eta = time_to_str(round((self.size - self.step) / speed)) + ' ETA'
        progress_text = self._progress_text(percentage, total, speed_str, eta)

        if self.first_write:
            self.first_write = False
            self._inject_to_iterm2(progress_text)
            return
        if self.tmux_pane_width > 0:
            self._inject_to_iterm2(f'\x1b[{self.columns}D{progress_text}')
        else:
            self._inject_to_iterm2(f'\r{progress_text}')

    def _get_speed(self, now):
        try:
            if self.speed_cnt <= SPEED_ARRAY_SIZE:
                self.speed_cnt += 1
                speed = (self.step - self.step_array[0]) / (now - self.time_array[0])
            else:
                speed = (self.step - self.step_array[self.speed_idx]) / (now - self.time_array[self.speed_idx])
        except ZeroDivisionError:
            speed = -1

        self.time_array[self.speed_idx] = now
        self.step_array[self.speed_idx] = self.step

        self.speed_idx += 1
        if self.speed_idx >= SPEED_ARRAY_SIZE:
            self.speed_idx %= SPEED_ARRAY_SIZE

        return speed

    def _progress_text(self, percentage, total, speed, eta):
        bar_min_len = 24
        left = f'({self.idx}/{self.num}) {self.name}' if self.num > 1 else self.name
        left_len = display_length(left)
        right = f' {percentage} | {total} | {speed} | {eta}'
        while True:
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            if left_len > 50:
                left, left_len = ellipsis_string(left, 50)
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            if left_len > 40:
                left, left_len = ellipsis_string(left, 40)
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            right = f' {percentage} | {speed} | {eta}'
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            if left_len > 30:
                left, left_len = ellipsis_string(left, 30)
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            right = f' {percentage} | {eta}'
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            right = f' {percentage}'
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            if left_len > 20:
                left, left_len = ellipsis_string(left, 20)
            if self.columns - left_len - len(right) >= bar_min_len:
                break
            left, left_len = '', 0
            break
        bar_len = self.columns - len(right)
        if left_len > 0:
            bar_len -= left_len + 1
            left += ' '
        return (left + self._progress_bar(bar_len) + right).strip()

    def _progress_bar(self, bar_len):
        if bar_len < 12:
            return ''
        total = bar_len - 2
        complete = round(total * self.step / self.size)
        return '[\u001b[36m' + '\u2588' * complete + '\u2591' * (total - complete) + '\u001b[0m]'

    def _inject_to_iterm2(self, data):
        self.loop.create_task(self.session.async_inject(data.encode('utf8')))
