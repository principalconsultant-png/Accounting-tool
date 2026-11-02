"""Offline native Tk calendar for editable ISO dates and month periods."""
import calendar
import re
from datetime import date,datetime
import tkinter as tk
from tkinter import ttk,simpledialog
from .history import INDIA


def today():return datetime.now(INDIA).date()

def date_mode(label,default=''):
    label=label.lower();text=str(default or '')
    if 'dates' in label and 'comma-separated' in label:return 'days'
    if any(w in label for w in ('format','column','reason','basis','threshold','days','period starts')):return None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):return 'day'
    if 'yyyy-mm' in label and 'yyyy-mm-dd' not in label:return 'month'
    if re.search(r'\b(date|from|through|as at|effective|due|completed|put.to.use)\b',label) or 'yyyy-mm-dd' in label:return 'day'
    return None


class CalendarPopup(tk.Toplevel):
    def __init__(self,parent,variable,mode='day'):
        super().__init__(parent);self.variable=variable;self.mode=mode;self.title('Choose month' if mode=='month' else 'Choose date');self.transient(parent.winfo_toplevel());self.resizable(False,False)
        self.previous_grab=self.grab_current()
        try:selected=date.fromisoformat((variable.get().split(',')[-1].strip() if mode=='days' else variable.get())+('-01' if mode=='month' else ''))
        except (ValueError,TypeError):selected=datetime.now(INDIA).date()
        self.year=selected.year;self.month=selected.month
        top=ttk.Frame(self,padding=8);top.pack(fill='x');ttk.Button(top,text='‹',width=3,command=lambda:self.move(-1)).pack(side='left');self.caption=ttk.Label(top,width=23,anchor='center');self.caption.pack(side='left');ttk.Button(top,text='›',width=3,command=lambda:self.move(1)).pack(side='left')
        jump=ttk.Frame(self,padding=5);jump.pack(fill='x');self.jumpyear=tk.StringVar(value=str(self.year));self.jumpmonth=tk.StringVar(value=calendar.month_name[self.month]);ttk.Spinbox(jump,from_=1,to=9999,textvariable=self.jumpyear,width=6).pack(side='left');ttk.Combobox(jump,textvariable=self.jumpmonth,values=list(calendar.month_name)[1:],state='readonly',width=13).pack(side='left');ttk.Button(jump,text='Go',command=self.jump).pack(side='left');self.date_error=ttk.Label(self,text='');self.date_error.pack()
        self.gridbody=ttk.Frame(self,padding=8);self.gridbody.pack();bar=ttk.Frame(self,padding=8);bar.pack(fill='x');ttk.Button(bar,text='Today',command=lambda:self.choose(datetime.now(INDIA).date())).pack(side='left');ttk.Button(bar,text='Clear',command=lambda:self.finish('')).pack(side='left');ttk.Button(bar,text='Cancel',command=self.close).pack(side='right')
        self.bind('<Escape>',lambda e:self.close());self.protocol('WM_DELETE_WINDOW',self.close);self.draw();self.grab_set()
    def move(self,delta):
        value=self.year*12+self.month-1+delta;y,m=divmod(value,12)
        if 1<=y<=9999:self.year,self.month=y,m+1;self.draw()
    def jump(self):
        try:y=int(self.jumpyear.get());m=list(calendar.month_name).index(self.jumpmonth.get());assert 1<=y<=9999 and 1<=m<=12
        except (ValueError,AssertionError):self.date_error.configure(text='Choose a year from 1 to 9999 and a month.');return
        self.year,self.month=y,m;self.date_error.configure(text='');self.draw()
    def draw(self):
        for child in self.gridbody.winfo_children():child.destroy()
        self.caption.configure(text=calendar.month_name[self.month]+' '+str(self.year));self.jumpyear.set(str(self.year));self.jumpmonth.set(calendar.month_name[self.month])
        if self.mode=='month':ttk.Button(self.gridbody,text='Select '+calendar.month_name[self.month],command=lambda:self.finish(f'{self.year:04}-{self.month:02}')).grid(row=0,column=0);return
        for col,label in enumerate(('Mon','Tue','Wed','Thu','Fri','Sat','Sun')):ttk.Label(self.gridbody,text=label).grid(row=0,column=col)
        for row,week in enumerate(calendar.monthcalendar(self.year,self.month),1):
            for col,n in enumerate(week):
                if n:ttk.Button(self.gridbody,text=str(n),width=4,command=lambda n=n:self.choose(date(self.year,self.month,n))).grid(row=row,column=col,padx=1,pady=1)
    def choose(self,value):
        text=value.strftime('%Y-%m' if self.mode=='month' else '%Y-%m-%d')
        if self.mode=='days':text=', '.join(sorted(set([v.strip() for v in self.variable.get().split(',') if v.strip()]+[text])))
        self.finish(text)
    def finish(self,value):self.variable.set(value);self.close()
    def close(self):
        self.destroy()
        if self.previous_grab is not None:
            try:self.previous_grab.grab_set()
            except tk.TclError:pass


def attach(entry,variable,mode='day'):
    button=ttk.Button(entry.master,text='Cal',width=3,command=lambda:CalendarPopup(entry,variable,mode));button.pack(side='left',padx=(3,0));entry.date_picker=button;return button


def ask_date(title,prompt,initialvalue='',parent=None):
    class Dialog(simpledialog.Dialog):
        def body(self,master):
            ttk.Label(master,text=prompt,wraplength=650).pack(anchor='w');self.value=tk.StringVar(value=initialvalue);row=ttk.Frame(master);row.pack(fill='x');entry=ttk.Entry(row,textvariable=self.value,width=18);entry.pack(side='left');attach(entry,self.value,'month' if 'YYYY-MM' in prompt and 'YYYY-MM-DD' not in prompt else 'day');return entry
        def apply(self):self.result=self.value.get().strip()
    return Dialog(parent,title).result


def insert_date_button(parent,textwidget,label='Insert calendar date'):
    def pick():
        variable=tk.StringVar(value='')
        def selected(*args):
            if variable.get():textwidget.insert('insert',variable.get())
        variable.trace_add('write',selected);CalendarPopup(textwidget,variable)
    button=ttk.Button(parent,text=label,command=pick);button.pack(anchor='w');return button
