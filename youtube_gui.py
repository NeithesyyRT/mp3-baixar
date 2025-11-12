import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
import threading
import subprocess
import os
import sys
import re
from concurrent.futures import ThreadPoolExecutor
from queue import Queue # Importação necessária para a fila de comunicação

# PRÉ-REQUISITOS (Obrigatórios):
# 1. Instalar o yt-dlp: pip install yt-dlp
# 2. Instalar o ffmpeg: Necessário para a conversão para MP3. Deve estar no PATH do sistema.

class YouTubeDownloaderApp:
    def __init__(self, master):
        self.master = master
        master.title("Downloader de MP3 em Lote - Estilo Moderno e Interativo")
        master.minsize(650, 580)
        master.resizable(True, True)

        # --- Variáveis de Controle de Estado e Interrupção ---
        self.is_downloading = False
        self.stop_event = threading.Event()
        self.active_processes = {}
        self.max_workers = 4
        self.YTDLP_EXECUTABLE = [sys.executable, '-m', 'yt_dlp']
        
        # --- NOVO: Fila de comunicação para Thread-Safe UI Updates ---
        # (tipo, url, mensagem)
        self.ui_update_queue = Queue() 
        self.check_queue_interval = 50 # Verifica a fila a cada 50ms
        
        # --- Configuração de Estilo Dark Moderno ---
        self.style = ttk.Style(self.master)
        
        # Variáveis de Cores
        BACKGROUND_DARK = '#212121'  
        FOREGROUND_LIGHT = '#F0F0F0'
        ACCENT_RED = '#DC3545'
        LOG_BG = '#121212'
        ACCENT_YELLOW = '#FFC107' 
        
        master.config(bg=BACKGROUND_DARK)
        self.style.theme_use('clam')
        
        # 1. Estilo Global e Frames
        self.style.configure('.', background=BACKGROUND_DARK, foreground=FOREGROUND_LIGHT, borderwidth=0)
        self.style.configure('TLabel', background=BACKGROUND_DARK, foreground=FOREGROUND_LIGHT, font=("Helvetica", 10))
        self.style.configure('TFrame', background=BACKGROUND_DARK)
        self.style.configure('Title.TLabel', font=("Helvetica", 16, "bold"), foreground=ACCENT_RED, background=BACKGROUND_DARK)
        
        # 2. Botão Principal (START - Vermelho)
        self.style.configure('Download.TButton', 
                             background=ACCENT_RED, 
                             foreground=FOREGROUND_LIGHT, 
                             font=("Helvetica", 13, "bold"), 
                             padding=[15, 12, 15, 12], 
                             relief='raised')
        self.style.map('Download.TButton', 
                         foreground=[('active', FOREGROUND_LIGHT), ('disabled', FOREGROUND_LIGHT)],
                         background=[('active', '#C82333'), ('disabled', '#343A40')]) 
        
        # 3. Botão Principal (STOP - Amarelo/Laranja)
        self.style.configure('Stop.TButton', 
                             background=ACCENT_YELLOW, 
                             foreground='#000000', 
                             font=("Helvetica", 13, "bold"), 
                             padding=[15, 12, 15, 12], 
                             relief='raised')
        self.style.map('Stop.TButton', 
                        foreground=[('active', '#000000'), ('disabled', FOREGROUND_LIGHT)],
                        background=[('active', '#E0A800'), ('disabled', '#343A40')]) 

        # 4. Progressbar
        self.style.configure("Red.Horizontal.TProgressbar", 
                             troughcolor='#333333',
                             background=ACCENT_RED, 
                             bordercolor=BACKGROUND_DARK)
        
        # 5. Combobox/Entry (Cores de Entrada)
        self.style.configure('Dark.TCombobox', 
                             fieldbackground='#333333', 
                             background='#444444', 
                             foreground=FOREGROUND_LIGHT,
                             selectbackground=ACCENT_RED, 
                             selectforeground=FOREGROUND_LIGHT)
        self.style.map('Dark.TCombobox',
                        fieldbackground=[('readonly', '#333333')],
                        foreground=[('readonly', FOREGROUND_LIGHT)])


        # Variáveis de Controle da GUI
        default_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(default_dir, exist_ok=True)
        self.output_dir_var = tk.StringVar(value=default_dir)
        self.audio_quality_var = tk.StringVar(value='0 (320 kbps - Melhor)')
        
        self.progress_count = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="")

        # Dicionário para rastrear o progresso individual de cada URL
        self.individual_progress = {} 
        self.individual_progress_lock = threading.Lock()
        
        self.create_widgets()
        
        # Configuração de Cores para o Log Interativo
        self.log_text.tag_config('success', foreground='#00FF7F')
        self.log_text.tag_config('error', foreground='#FF6347')
        self.log_text.tag_config('warn', foreground='#FFD700')
        self.log_text.tag_config('info', foreground='#00BFFF')
        self.log_text.tag_config('process', foreground='#E0E0E0')
        self.log_internal(f"Pronto. Downloads simultâneos limitados a {self.max_workers} processos.", 'info')

        # Inicia o loop de verificação da fila de eventos
        self.master.after(self.check_queue_interval, self.check_ui_queue)


    # --- Funções de Log e Utilidade ---
    def log_internal(self, message, level='process'):
        """Adiciona uma mensagem ao console de log e aplica a cor (somente thread principal)."""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n", level)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.master.update_idletasks() # Atualiza imediatamente para responsividade

    def log_message(self, message, level='process'):
        """Thread-safe: Adiciona mensagem à fila para processamento na thread principal."""
        self.ui_update_queue.put(('LOG', None, (message, level)))

    def select_output_directory(self):
        new_dir = filedialog.askdirectory(
            title="Selecione o Diretório de Saída",
            initialdir=self.output_dir_var.get()
        )
        if new_dir:
            self.output_dir_var.set(new_dir)
            self.log_internal(f"Diretório de saída alterado para: {new_dir}", 'info')
            
    def get_audio_quality_flag(self):
        return self.audio_quality_var.get().split(' ')[0]

    def update_progress_text(self, total):
        """Atualiza o texto de progresso geral (Thread Principal)."""
        completed = int(self.progress_count.get())
        if total > 0:
            self.progress_text_var.set(f"Progresso do Lote: {completed} de {total} itens concluídos.")
        else:
            self.progress_text_var.set("")

    # --- Gerenciamento de UI de Progresso Individual ---
    def create_individual_progress_ui(self, url):
        """Cria a UI para uma única tarefa de download/conversão (Thread Principal)."""
        
        with self.individual_progress_lock:
            if url in self.individual_progress:
                return

            row_num = len(self.individual_progress)
            
            # 1. Frame para o item (Label + Bar)
            item_frame = ttk.Frame(self.progress_display_frame)
            item_frame.grid(row=row_num, column=0, sticky='ew', pady=2)
            self.progress_display_frame.grid_columnconfigure(0, weight=1)

            # 2. Variáveis de Estado
            progress_var = tk.DoubleVar(value=0.0)
            label_var = tk.StringVar(value=f"⏳ {url[:60]}... (0.0%)")

            # 3. Label de Título/Status
            title_label = ttk.Label(item_frame, textvariable=label_var, anchor='w', font=("Helvetica", 9, "bold"))
            title_label.grid(row=0, column=0, sticky='ew')

            # 4. Barra de Progresso
            progress_bar = ttk.Progressbar(item_frame, orient='horizontal', mode='determinate', 
                                         style="Red.Horizontal.TProgressbar", variable=progress_var)
            progress_bar.grid(row=1, column=0, sticky='ew')

            # 5. Armazenamento
            self.individual_progress[url] = {
                'var': progress_var,
                'label_var': label_var,
                'frame': item_frame,
                'bar': progress_bar
            }
            
    def remove_individual_progress_ui(self, url):
        """Remove a UI de uma tarefa de download/conversão concluída (Thread Principal)."""
        with self.individual_progress_lock:
            if url in self.individual_progress:
                self.individual_progress[url]['frame'].destroy()
                del self.individual_progress[url]
                
                # Reposiciona os elementos restantes para preencher o espaço
                for i, (url, data) in enumerate(self.individual_progress.items()):
                    data['frame'].grid(row=i, column=0, sticky='ew', pady=2)

    def parse_and_update_progress(self, url, line):
        """Atualiza a barra de progresso individual baseada na linha de log (Thread Principal)."""
        
        with self.individual_progress_lock:
            if url not in self.individual_progress:
                return 

            data = self.individual_progress[url]

            progress_match = re.search(r'\[download\]\s+(\d+\.\d+)%', line)
            if progress_match:
                percent = float(progress_match.group(1))
                # Tenta extrair status, se falhar usa a linha inteira
                status_text = line.split('[download]')[1].strip() if '[download]' in line else line.strip()
                data['var'].set(percent)
                data['label_var'].set(f"⬇️ {url[:60]}... ({percent:.1f}%) - {status_text}")
            elif 'Post-processing' in line:
                data['label_var'].set(f"🔄 {url[:60]}... (100%) - Conversão para MP3...")
                data['var'].set(99.0)
            
            self.log_internal(line.strip(), 'process')
    
    # --- NOVO: Verificador de Fila de Eventos ---
    def check_ui_queue(self):
        """
        Verifica a fila de eventos e processa todas as mensagens de forma segura 
        na thread principal para evitar congelamento.
        """
        try:
            while not self.ui_update_queue.empty():
                item = self.ui_update_queue.get_nowait()
                msg_type, url, data = item
                
                if msg_type == 'LOG':
                    message, level = data
                    self.log_internal(message, level)
                elif msg_type == 'CREATE_UI':
                    self.create_individual_progress_ui(url)
                elif msg_type == 'UPDATE_PROGRESS':
                    line = data
                    self.parse_and_update_progress(url, line)
                elif msg_type == 'REMOVE_UI':
                    self.remove_individual_progress_ui(url)
                elif msg_type == 'UPDATE_BATCH':
                    total_items = data
                    self.update_progress_text(total_items)
                elif msg_type == 'INCREMENT_COUNT':
                    total_items = data
                    self.progress_count.set(self.progress_count.get() + 1.0)
                    self.update_progress_text(total_items)
                    
        except Exception as e:
            # Em caso de erro na fila, loga e continua
            print(f"Erro ao processar fila da UI: {e}") 
        finally:
            # Agenda a próxima verificação
            self.master.after(self.check_queue_interval, self.check_ui_queue)
            
    # --- Interação Principal e Controle de Estado ---
    
    def handle_main_action(self):
        """Gerencia o estado do botão (Iniciar/Parar)."""
        if self.is_downloading:
            self.stop_downloads()
        else:
            self.start_downloads()

    def stop_downloads(self):
        """Sinaliza e tenta encerrar processos ativos."""
        if not self.is_downloading:
            return

        self.log_message("🚨 [INTERRUPÇÃO] Sinal de parada enviado. Tentando encerrar processos ativos...", 'warn')
        self.stop_event.set() 
        
        # Tentativa de Terminar Processos
        for url, process in list(self.active_processes.items()): 
            if process.poll() is None: 
                try:
                    process.terminate() 
                    self.log_message(f"🚫 Terminado: {url[:40]}...", 'warn')
                except Exception as e:
                    self.log_message(f"Erro ao terminar processo {url[:40]}: {e}", 'error')

        # Desabilita o botão até a finalização completa na thread orquestradora
        self.download_button.config(state='disabled', text="Aguardando threads finalizarem...")


    def start_downloads(self):
        """Inicia a validação e o thread principal de orquestração."""
        urls = self.url_text.get(1.0, tk.END).strip()
        url_list = [url.strip() for url in urls.splitlines() if url.strip()]
        
        if not url_list:
            messagebox.showerror("Erro", "Por favor, cole pelo menos uma URL de vídeo ou playlist.")
            return

        # --- Configuração de Estado ---
        self.is_downloading = True
        self.stop_event.clear()
        self.active_processes = {}

        # --- Configuração de UI (Modo STOP) ---
        self.download_button.config(style='Stop.TButton', text="🛑 Parar Downloads")
        self.download_button.config(state='normal')
        
        self.progress_bar.config(maximum=len(url_list))
        self.progress_count.set(0.0)
        
        # Adiciona à fila
        self.ui_update_queue.put(('UPDATE_BATCH', None, len(url_list)))
        
        self.log_message("-" * 40, 'warn')
        self.log_message("Iniciando o processo de download em segundo plano...", 'warn')
        self.log_message(f"Total de {len(url_list)} itens a serem processados.", 'info')
        self.log_message("-" * 40, 'warn')

        download_orchestrator_thread = threading.Thread(target=self.orchestrate_downloads, args=(url_list,))
        download_orchestrator_thread.start()

    # --- Funções de Processamento ---
    def download_single_url(self, url, output_dir, audio_quality_flag, total_items):
        """Lógica de download para uma única URL em uma thread."""
        
        # Envia comando para criar a UI individual na thread principal
        self.ui_update_queue.put(('CREATE_UI', url, None))

        if self.stop_event.is_set():
            self.log_message(f"🚫 [CANCELADO] Pulando {url[:40]}... (Orquestrador Parou)", 'warn')
            self.ui_update_queue.put(('REMOVE_UI', url, None))
            return

        self.log_message(f"[INÍCIO] Processando URL: {url[:50]}...", 'process')
        
        CONCURRENT_FRAGMENTS = '64' 
        
        command = self.YTDLP_EXECUTABLE + [
            '-x',
            '--audio-format', 'mp3',
            '--audio-quality', audio_quality_flag,
            '--concurrent-fragments', CONCURRENT_FRAGMENTS, 
            '-f', 'bestaudio/best', 
            '-o', os.path.join(output_dir, '%(title)s.%(ext)s'),
            url
        ]
        
        process = None
        try:
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                bufsize=1
            )
            
            self.active_processes[url] = process

            # Log em tempo real, parse e checagem de interrupção
            for line in iter(process.stdout.readline, ''):
                if self.stop_event.is_set():
                    self.log_message(f"🚫 [INTERROMPENDO] Encerrando subprocesso de {url[:40]}...", 'warn')
                    process.terminate()
                    break 

                # NOVO: Envia a linha para a fila. A thread principal fará o parse e a atualização da UI.
                self.ui_update_queue.put(('UPDATE_PROGRESS', url, line))

            process.stdout.close()
            return_code = process.wait()

            # Atualização de Progresso Geral e Log Final
            if not self.stop_event.is_set() and return_code == 0:
                self.ui_update_queue.put(('INCREMENT_COUNT', None, total_items))
                self.log_message(f"✅ [SUCESSO] Concluído: {url[:50]}...", 'success')
            elif not self.stop_event.is_set() and return_code != 0:
                self.ui_update_queue.put(('INCREMENT_COUNT', None, total_items))
                self.log_message(f"❌ [FALHA] URL falhou com código {return_code}: {url[:50]}...", 'warn')
                
        except Exception as e:
            self.ui_update_queue.put(('INCREMENT_COUNT', None, total_items))
            self.log_message(f"🚨 [ERRO FATAL] Falha em {url[:50]}: {e}", 'error')
        
        finally:
            if url in self.active_processes:
                del self.active_processes[url]
            
            # Envia comando para remover a UI individual
            self.ui_update_queue.put(('REMOVE_UI', url, None))
            
    def orchestrate_downloads(self, url_list):
        """Orquestra os downloads usando um Pool de Threads."""
        output_dir = self.output_dir_var.get()
        audio_quality_flag = self.get_audio_quality_flag()
        total_items = len(url_list)
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self.download_single_url, url, output_dir, audio_quality_flag, total_items)
                           for url in url_list]
                
                # Aguarda todos os futures, mas permite interrupção/exceções
                for future in futures:
                    try:
                        future.result() 
                    except Exception as e:
                        self.log_message(f"🚨 [ERRO NA THREAD DE DOWNLOAD]: {e}", 'error')


        except Exception as e:
            self.log_message(f"🚨 [ERRO FATAL NO ORQUESTRADOR]: {e}", 'error')
        finally:
            # Chama a finalização da thread principal
            self.master.after(0, self.finalize_download_process)

    def finalize_download_process(self):
        """Restaura o estado da UI e loga a conclusão (Thread Principal)."""
        self.is_downloading = False
        self.stop_event.clear() 
        self.active_processes = {}

        self.log_internal("=" * 40, 'warn')
        if self.progress_count.get() == self.progress_bar['maximum']:
            self.log_internal("🎉 PROCESSO DE LOTE CONCLUÍDO.", 'success')
        else:
             self.log_internal("🚫 PROCESSO DE LOTE INTERROMPIDO. Veja o log acima para os itens cancelados.", 'warn')
        
        self.log_internal("=" * 40, 'warn')
        
        self.download_button.config(
                          {'state': 'normal', 
                           'text': "🚀 Iniciar Download & Conversão para MP3",
                           'style': 'Download.TButton'})


    # --- Criação dos Widgets ---
    def create_widgets(self):
        BACKGROUND_DARK = '#212121'
        FOREGROUND_LIGHT = '#F0F0F0'
        LOG_BG = '#121212'
        ACCENT_YELLOW = '#FFC107'
        
        main_frame = ttk.Frame(self.master, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky='nsew')

        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Título (Linha 0)
        title_label = ttk.Label(main_frame, text="🎵 Downloader de YouTube para MP3 em Lote", style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky='n', pady=(0, 15))
        
        # Linha 1: Seleção de Diretório de Saída
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=0, sticky='ew', pady=5)
        path_frame.grid_columnconfigure(1, weight=1) 
        
        ttk.Label(path_frame, text="Salvar em:", anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        
        # Corrigido: usando tk.Entry, não ttk.Entry, e sem ipady.
        dir_entry = tk.Entry(path_frame, textvariable=self.output_dir_var, state='readonly', width=55, 
                             bg='#333333', fg=FOREGROUND_LIGHT, bd=0, relief=tk.FLAT,
                             readonlybackground='#333333', disabledforeground=FOREGROUND_LIGHT)
        
        dir_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=5) 
        
        ttk.Button(path_frame, text="📁 Procurar...", command=self.select_output_directory).pack(side=tk.RIGHT)
        
        # Linha 2: Configuração de Qualidade
        config_frame = ttk.Frame(main_frame)
        config_frame.grid(row=2, column=0, sticky='w', pady=5)
        
        ttk.Label(config_frame, text="Qualidade MP3:", anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        
        quality_options = ['0 (320 kbps - Melhor)', '5 (192 kbps - Padrão)', '10 (128 kbps - Econômico)']
        self.quality_combobox = ttk.Combobox(config_frame, textvariable=self.audio_quality_var, values=quality_options, state='readonly', width=30, style='Dark.TCombobox')
        self.quality_combobox.pack(side=tk.LEFT)
        self.quality_combobox.current(0)

        # Linha 3: Entrada de URLs Label
        ttk.Label(main_frame, text="🔗 Cole as URLs dos vídeos/playlists (uma por linha):", anchor='w').grid(row=3, column=0, sticky='ew', pady=(10, 2))

        # Linha 4: Entrada de URLs Text Area
        self.url_text = scrolledtext.ScrolledText(main_frame, height=8, width=50, wrap=tk.WORD, font=("Arial", 10), 
                                                 bg='#333333', fg=FOREGROUND_LIGHT, insertbackground=FOREGROUND_LIGHT, bd=0, padx=8, pady=8)
        self.url_text.grid(row=4, column=0, sticky='nsew', padx=0, pady=5)
        main_frame.grid_rowconfigure(4, weight=1) 

        # Linha 5: Feedback de Otimização
        optimization_frame = ttk.Frame(main_frame)
        optimization_frame.grid(row=5, column=0, sticky='ew', pady=5)
        ttk.Label(optimization_frame, text=f"⚡ Otimização: {self.max_workers} downloads simultâneos e 64 fragmentos concorrentes ativados.", 
                  foreground=ACCENT_YELLOW, background='#444444', padding="5").pack(fill='x')

        # Linha 6: Botão de Download
        self.download_button = ttk.Button(main_frame, text="🚀 Iniciar Download & Conversão para MP3", 
                                          command=self.handle_main_action, 
                                          style='Download.TButton')
        self.download_button.grid(row=6, column=0, sticky='ew', pady=15, padx=0)

        # Linha 7: Status do Processo Label
        ttk.Label(main_frame, text="Status do Processo:", anchor='w').grid(row=7, column=0, sticky='ew', pady=(5, 2))
        
        # Linha 8: Progressbar Geral
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', mode='determinate', 
                                            style="Red.Horizontal.TProgressbar", variable=self.progress_count)
        self.progress_bar.grid(row=8, column=0, sticky='ew', padx=0, pady=2)
        
        # Linha 9: Texto de Progresso Detalhado
        ttk.Label(main_frame, textvariable=self.progress_text_var, anchor='w', foreground='#909090').grid(row=9, column=0, sticky='w', pady=(2, 5))
        
        # Linha 10: Progresso Individual Label
        ttk.Label(main_frame, text="Progresso Individual:", anchor='w', foreground=ACCENT_YELLOW).grid(row=10, column=0, sticky='ew', pady=(10, 2))

        # Linha 11: Frame para Progresso Individual (Onde as barras dinâmicas serão adicionadas)
        self.progress_display_frame = ttk.Frame(main_frame)
        self.progress_display_frame.grid(row=11, column=0, sticky='ew', padx=0, pady=5)
        
        # Linha 12: Log Console (Expansível)
        self.log_text = scrolledtext.ScrolledText(main_frame, height=8, width=50, wrap=tk.WORD, font=("Consolas", 9), 
                                                 state='disabled', bg=LOG_BG, fg='#E0E0E0', bd=0, padx=10, pady=10)
        self.log_text.grid(row=12, column=0, sticky='nsew', padx=0, pady=5)
        main_frame.grid_rowconfigure(12, weight=1)


if __name__ == '__main__':
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()