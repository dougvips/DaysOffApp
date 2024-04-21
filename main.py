from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from datetime import datetime, timedelta
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.properties import ListProperty
from kivy.utils import platform
from kivy.metrics import dp, sp
import locale

size = dp(100)  # 100 dp (densidade independente de pixels)
font_size = sp(20)  # 20 sp (escala independente de pixels para fontes)

# Tente configurar o local para pt_BR.UTF-8
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    # Se o local pt_BR.UTF-8 não estiver disponível, utilize o padrão do sistema
    locale.setlocale(locale.LC_ALL, '')

class DateInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def insert_text(self, substring, from_undo=False):
        if len(self.text) + len(substring) > 10 or (not substring.isdigit() and substring not in ['/', '']):
            return
        if self.text.endswith('/') and substring == '/':
            return
        elif len(self.text) == 1 or len(self.text) == 4:
            substring = f'{substring}/'
        super(DateInput, self).insert_text(substring, from_undo=from_undo)

        # Agora chamaremos uma função de verificação após a inserção completa da data
        # Em DateInput, após a verificação bem-sucedida da data
        if len(self.text) == 10:
            try:
                datetime.strptime(self.text, '%d/%m/%Y')
                App.get_running_app().root.check_for_extra_date_field()
            except ValueError:
                pass

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        # Detecta se a tecla Tab foi pressionada
        if keycode[1] == 'tab':  # keycode[1] é a representação string da tecla
            next = self.get_focus_next()
            if next:
                next.focus = True
            return True  # Consumir o evento para evitar propagação
        return super(DateInput, self).keyboard_on_key_down(window, keycode, text, modifiers)

    def on_option_select(self, selected_option):
        self.text = selected_option
        app = App.get_running_app()
        app.root.remove_extra_fields()  # Remove campos extras antes de adicionar novos
        app.root.update_tipo_escala(selected_option)

def calculate_days_until_next_offday(current_day, current_index, cycle_days):
    # Calcula o dia da semana para a próxima folga com base no ciclo
    next_offday_weekday = cycle_days[(current_index + 1) % len(cycle_days)]
    # Calcula quantos dias até a próxima folga
    days_until_next = (next_offday_weekday - current_day.weekday()) % 7
    if days_until_next == 0:  # Se for o mesmo dia da semana, pula para o próximo do mesmo tipo
        days_until_next = 7
    return days_until_next

def convert_day_to_number(day):
    days = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }
    return days.get(day)

def generate_off_days(start_date, end_date, off_days_pattern):
    off_days = []
    current_date = start_date
    pattern_numbers = [convert_day_to_number(day) for day in off_days_pattern]

    while current_date <= end_date:
        if current_date.weekday() in pattern_numbers:
            off_days.append(current_date)
        current_date += timedelta(days=1)
    return off_days

def generate_farma_off_days(start_date, end_date, next_off_day):
    # Representa Dom, Qui, Seg, Sex, Sab, Qua
    sequential_pattern = [6, 3, 0, 4, 5, 2]
    
    off_days = []
    current_day = next_off_day  # Inicia no próximo dia de folga conhecido

    # Acha o índice inicial no padrão baseado no dia da semana da próxima folga
    pattern_index = sequential_pattern.index(next_off_day.weekday())

    # Adiciona a primeira folga conhecida
    if start_date <= next_off_day <= end_date:
        off_days.append(next_off_day)

    # Continua calculando as próximas folgas até o final do período
    while current_day < end_date:
        # Calcula o próximo dia de folga
        next_day_of_week = sequential_pattern[(pattern_index + 1) % len(sequential_pattern)]
        days_until_next = (next_day_of_week - current_day.weekday() + 7) % 7
        if days_until_next == 0:
            days_until_next = 7  # Para garantir que não seja no mesmo dia
        
        current_day += timedelta(days=days_until_next)
        if current_day > end_date:
            break
        
        off_days.append(current_day)
        pattern_index = (pattern_index + 1) % len(sequential_pattern)

    return off_days

def generate_at1at2_off_days(start_date, end_date, next_off_day, last_off_day=None):
    off_days = [next_off_day]  # Inclui o próximo dia de folga conhecido
    current_day = next_off_day  # Começa a contagem a partir do próximo dia de folga

    while current_day <= end_date:
        # Define os dias até a próxima folga
        if last_off_day and last_off_day.weekday() == 3:  # Última folga foi uma quinta-feira
            if current_day.weekday() == 6:  # A próxima folga é um domingo, especial
                next_folga = current_day + timedelta(days=3)  # Avança 3 dias para a próxima folga na quarta-feira
            else:
                next_folga = current_day + timedelta(days=6)  # Retorna ao ciclo normal após quarta
        else:
            # Ciclo normal: 5 dias de trabalho, 1 de folga
            if current_day.weekday() == 3:  # Se a folga cair em uma quinta-feira, prepara para o ciclo especial
                next_folga = current_day + timedelta(days=3)  # A próxima folga será no domingo especial
            else:
                next_folga = current_day + timedelta(days=6)  # Continua com o ciclo normal de 6 dias

        if next_folga > end_date:
            break  # Sai do loop se a próxima folga estiver fora do intervalo de datas

        off_days.append(next_folga)  # Adiciona a próxima folga calculada à lista
        last_off_day = current_day  # Atualiza a última folga
        current_day = next_folga  # Atualiza o dia atual para o novo dia de folga

    return off_days

def generate_supervisor1_off_days(start_date, end_date, next_off_day, last_off_day=None):
    # Define the week day numbers
    days = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    # Define the cycle pattern: [Tuesday, Tuesday, Sunday, Friday]
    cycle_days = [1, 1, 6, 4]

    off_days = []
    current_index = 0

    # If there's a last off day provided, start the sequence after it
    if last_off_day:
        # Find the index of the next day in the cycle after the last off day
        last_index = cycle_days.index(last_off_day.weekday())
        current_index = (last_index + 1) % len(cycle_days)
        current_day = last_off_day + timedelta(days=1)
    else:
        # Start from the next known off day
        off_days.append(next_off_day)
        current_day = next_off_day + timedelta(days=1)
        current_index = (cycle_days.index(next_off_day.weekday()) + 1) % len(cycle_days)

    # Generate off days until the end date
    while current_day <= end_date:
        days_until_next = (cycle_days[current_index] - current_day.weekday() + 7) % 7
        if days_until_next == 0:
            days_until_next = 7  # Adjust to skip to the next valid day

        current_day += timedelta(days=days_until_next)
        if current_day <= end_date:
            off_days.append(current_day)

        current_index = (current_index + 1) % len(cycle_days)

    return off_days

def generate_supervisor2_days(start_date, end_date, next_off_day):
    # A sequência reflete: Domingo (6), Sábado (5), Quinta (3), Terça (1)
    sequential_pattern = [6, 5, 3, 1]
    
    off_days = []
    current_day = next_off_day  # Começa a contar a partir da próxima folga

    if start_date <= next_off_day <= end_date:
        off_days.append(next_off_day)  # Adiciona a próxima folga à lista se estiver dentro do intervalo

    # Encontra o índice do dia da semana da próxima folga dentro do padrão
    pattern_index = sequential_pattern.index(next_off_day.weekday())

    while current_day <= end_date:
        # Avança para o próximo índice no padrão sequencial
        pattern_index = (pattern_index + 1) % len(sequential_pattern)
        next_day_of_week = sequential_pattern[pattern_index]

        # Calcula os dias até a próxima folga
        days_until_next = (next_day_of_week - current_day.weekday() + 7) % 7
        if days_until_next == 0:
            days_until_next = 7  # Ajuste para garantir que estamos avançando para o próximo dia no padrão

        next_off_day = current_day + timedelta(days=days_until_next)
        
        if next_off_day > end_date:
            break  # Sai do loop se a próxima folga estiver fora do intervalo de datas

        off_days.append(next_off_day)
        current_day = next_off_day

    return off_days

from kivy.uix.scrollview import ScrollView

class GridDropDown(ModalView):
    def __init__(self, button_ref, options, **kwargs):
        super(GridDropDown, self).__init__(**kwargs)
        self.size_hint = (None, None)
        self.width = Window.width * 0.6
        self.auto_dismiss = False

        self.button_ref = button_ref

        grid_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        # Isso é necessário para que o GridLayout cresça com seu conteúdo:
        grid_layout.bind(minimum_height=grid_layout.setter('height'))

        scroll_view = ScrollView(size_hint=(1, None), size=(self.width, Window.height * 0.5))
        scroll_view.do_scroll_x = False  # Desabilita a rolagem horizontal

        for option in options:
            btn = Button(text=option, size_hint_y=None, height=40, size_hint_x=1)
            btn.bind(on_release=self.on_select)
            grid_layout.add_widget(btn)

        scroll_view.add_widget(grid_layout)  # Adicione o GridLayout ao ScrollView
        self.add_widget(scroll_view)

    def on_open(self):
        self.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

    def on_select(self, instance):
        self.button_ref.text = instance.text
        self.dismiss()
        self.button_ref.on_option_select(instance.text)

class CustomSpinnerButton(Button):
    options = ListProperty([])

    def __init__(self, **kwargs):
        super(CustomSpinnerButton, self).__init__(**kwargs)
        self.bind(on_release=self.open_dropdown)

    def open_dropdown(self, *args):
        dropdown = GridDropDown(button_ref=self, options=self.options)
        dropdown.open()

    def on_option_select(self, selected_option):
        app = App.get_running_app()
        self.text = selected_option  # Atualiza o texto do botão com a opção selecionada
        app.root.update_tipo_escala(selected_option)  # Atualiza o tipo de escala
        app.root.reset_state()  # Limpa apenas os campos extras
        app.root.check_for_extra_date_field()

class MainScreen(BoxLayout):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 5
        self.spacing = 10
        self.field_tuesday_added = False
        self.field_sunday_added = False
        self.extra_fields = []
        
        self.tipo_escala_button = CustomSpinnerButton(text='Tipo de Escala',font_size='15sp', options=["Atendente 1 e 2", "Farmacêutico(a)", "Supervisor(a) manhã", "Supervisor(a) noite", "Gerente"])
        self.add_widget(self.tipo_escala_button)

        self.nome_button = CustomSpinnerButton(text='Nome',font_size='15sp', options=["Brenda", "Bruno", "Douglas", "Evandro", "Felipe", "Giovana", "João", "Luan", "Marlene", "Ricardo"])
        self.add_widget(self.nome_button)

        # Adiciona os inputs sem referência a tipo_escala_spinner
        self.data_atual_input = DateInput(text='',font_size='15sp', hint_text='Data atual (dd/mm/aaaa)', multiline=False)
        self.add_widget(self.data_atual_input)

        self.data_final_input = DateInput(text='',font_size='15sp', hint_text='Data final (dd/mm/aaaa)', multiline=False)
        self.add_widget(self.data_final_input)

        self.proxima_folga_input = DateInput(font_size='15sp',hint_text='Próxima folga (dd/mm/aaaa)', multiline=False)
        self.add_widget(self.proxima_folga_input)

        self.submit_button = Button(text='Gerar Datas de Folga',font_size='20sp', on_press=self.submit_action)
        self.add_widget(self.submit_button)

    def update_tipo_escala(self, tipo_escala):
        self.tipo_escala_atual = tipo_escala

    def check_for_extra_date_field(self):
        # Remova todos os campos extras existentes primeiro
        self.remove_extra_fields()
        
        if self.proxima_folga_input.text:
            try:
                proxima_folga = datetime.strptime(self.proxima_folga_input.text, '%d/%m/%Y')
                tipo_escala_atual = self.tipo_escala_button.text
                
                # Verifica se precisa adicionar campos baseados na nova escala e data
                if tipo_escala_atual == "Supervisor(a) manhã" and proxima_folga.weekday() == 1:
                    self.add_previous_tuesday_field()
                elif tipo_escala_atual == "Atendente 1 e 2" and proxima_folga.weekday() == 6:
                    self.add_previous_sunday_field()
            except ValueError:
                pass  # Tratar erro de data inválida se necessário

    def reset_state(self):
        # Remova todos os campos extras quando resetar o estado
        self.remove_extra_fields()
        self.field_tuesday_added = False
        self.field_sunday_added = False

    def add_previous_tuesday_field(self):
        # Cria e adiciona o campo de entrada para a última folga se ainda não existir
        if not hasattr(self, 'previous_tuesday_input'):
            self.previous_tuesday_input = DateInput(hint_text='Folga anterior à Terça-Feira (dd/mm/aaaa)', multiline=False)
            # Calcula a posição correta para inserir o novo campo logo após 'Próxima Folga'
            position = self.children.index(self.proxima_folga_input) + 0
            self.add_widget(self.previous_tuesday_input, position)
            self.extra_fields.append(self.previous_tuesday_input)
        else:
            # Se o campo já foi adicionado antes, apenas garanta que ele esteja visível sem recriá-lo
            self.previous_tuesday_input.opacity = 1
            self.previous_tuesday_input.disabled = False

    def add_previous_sunday_field(self):
        # Cria e adiciona o campo de entrada para a última folga se ainda não existir
        if not hasattr(self, 'previous_sunday_input'):
            self.previous_sunday_input = DateInput(hint_text='Folga aterior ao Domingo (dd/mm/aaaa)', multiline=False)
            # Calcula a posição correta para inserir o novo campo logo após 'Próxima Folga'
            position = self.children.index(self.proxima_folga_input) + 0
            self.add_widget(self.previous_sunday_input, position)
            self.extra_fields.append(self.previous_sunday_input)
        else:
            # Se o campo já foi adicionado antes, apenas garanta que ele esteja visível sem recriá-lo
            self.previous_sunday_input.opacity = 1
            self.previous_sunday_input.disabled = False

    def remove_extra_fields(self):
        # Remove todos os campos extras da tela
        for field in self.extra_fields:
            self.remove_widget(field)
        self.extra_fields.clear()
        self.field_sunday_added = False



    def submit_action(self, instance):
        start_date_str = self.data_atual_input.text
        end_date_str = self.data_final_input.text
        proxima_folga_str = self.proxima_folga_input.text
        tipo_escala = self.tipo_escala_button.text

        try:
            start_date = datetime.strptime(start_date_str, '%d/%m/%Y')
            end_date = datetime.strptime(end_date_str, '%d/%m/%Y')
            next_off_day = datetime.strptime(proxima_folga_str, '%d/%m/%Y')

            last_off_day = None  # Se necessário, pode ser definido ou calculado dependendo da lógica de negócios

            if tipo_escala == "Supervisor(a) manhã":
                if hasattr(self, 'previous_tuesday_input') and self.previous_tuesday_input.text:
                    last_off_day = datetime.strptime(self.previous_tuesday_input.text, '%d/%m/%Y')
                off_days = generate_supervisor1_off_days(start_date, end_date, next_off_day, last_off_day)
            elif tipo_escala == "Atendente 1 e 2":
                if hasattr(self, 'previous_sunday_input') and self.previous_sunday_input.text:
                    last_off_day = datetime.strptime(self.previous_sunday_input.text, '%d/%m/%Y')
                off_days = generate_at1at2_off_days(start_date, end_date, next_off_day, last_off_day)
            elif tipo_escala == "Farma":
                off_days = generate_farma_off_days(start_date, end_date, next_off_day)
            elif tipo_escala == "Supervisor(a) noite":
                off_days = generate_supervisor2_days(start_date, end_date, next_off_day)

            off_days_formatted = [day.strftime('%d/%m/%Y (%A)') for day in off_days]
            popup_content = Label(text='\n'.join(off_days_formatted), halign='center')
            popup = Popup(title='Datas de Folga', content=popup_content, size_hint=(0.9, 0.9))
            popup.open()

        except ValueError as e:
            popup_content = Label(text=str(e), halign='center')
            popup = Popup(title='Erro', content=popup_content, size_hint=(0.8, 0.4))
            popup.open()

class DaysOffApp(App):
    def build(self):
        if platform != 'android':
            Window.size = (300, 600)

        return MainScreen()

if __name__ == '__main__':
    DaysOffApp().run()