import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
import threading
import subprocess
import os
import sys

# PRÉ-REQUISITOS (Obrigatórios):
# 1. Instalar o yt-dlp: pip install yt-dlp
# 2. Instalar o ffmpeg: Necessário para a conversão para MP3. Deve estar no PATH do sistema.

class YouTubeDownloaderApp:
    def __init__(self, master):
        self.master = master
        master.title("Downloader de MP3 em Lote - Estilo Moderno e Interativo")
        # master.geometry("650x580") # Removido para permitir redimensionamento
        master.minsize(650, 580)  # Define um tamanho mínimo para garantir a legibilidade
        master.resizable(True, True) # Habilitado o redimensionamento
        
        # --- Configuração de Estilo Dark Moderno ---
        self.style = ttk.Style(self.master)
        
        # Variáveis de Cores (baseadas no Gray 900, Red 600 e log verde)
        BACKGROUND_DARK = '#212121'  
        FOREGROUND_LIGHT = '#F0F0F0'
        ACCENT_RED = '#DC3545'
        LOG_BG = '#121212'
        
        # Aplica cor de fundo à janela principal
        master.config(bg=BACKGROUND_DARK)
        
        self.style.theme_use('clam')
        
        # 1. Estilo Global e Frames
        self.style.configure('.', background=BACKGROUND_DARK, foreground=FOREGROUND_LIGHT, borderwidth=0)
        self.style.configure('TLabel', background=BACKGROUND_DARK, foreground=FOREGROUND_LIGHT, font=("Helvetica", 10))
        self.style.configure('TFrame', background=BACKGROUND_DARK)
        
        # 2. Configuração do Título
        self.style.configure('Title.TLabel', font=("Helvetica", 16, "bold"), foreground=ACCENT_RED, background=BACKGROUND_DARK)
        
        # 3. Botão Principal (Destaque Vermelho)
        # Aumentamos o padding para um visual mais arredondado/cheio
        self.style.configure('Download.TButton', 
                             background=ACCENT_RED, 
                             foreground=FOREGROUND_LIGHT, 
                             font=("Helvetica", 13, "bold"), # Fonte um pouco maior
                             padding=[15, 12, 15, 12],      # Padding aumentado (horizontal, vertical)
                             relief='raised')
        self.style.map('Download.TButton', 
                        foreground=[('active', FOREGROUND_LIGHT), ('disabled', FOREGROUND_LIGHT)],
                        background=[('active', '#C82333'), ('disabled', '#343A40')]) 
        
        # 4. Progressbar (Acento em Vermelho)
        self.style.configure("Red.Horizontal.TProgressbar", 
                             troughcolor='#333333',
                             background=ACCENT_RED, 
                             bordercolor=BACKGROUND_DARK)
        
        # 5. ESTILOS PARA CORREÇÃO DE CORES DA ENTRADA E COMBOBOX
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
        self.YTDLP_EXECUTABLE = [sys.executable, '-m', 'yt_dlp']
        
        default_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(default_dir, exist_ok=True)
        self.output_dir_var = tk.StringVar(value=default_dir)
        self.audio_quality_var = tk.StringVar(value='0 (320 kbps - Melhor)')
        
        # VARIÁVEIS DE INTERATIVIDADE E PROGRESSO
        self.progress_count = tk.DoubleVar(value=0.0) # Progresso de downloads completos (determinado)
        self.progress_text_var = tk.StringVar(value="")
        
        self.create_widgets()
        
        # Configuração de Cores para o Log Interativo
        self.log_text.tag_config('success', foreground='#00FF7F') # Verde Brilhante
        self.log_text.tag_config('error', foreground='#FF6347')   # Vermelho Cobre
        self.log_text.tag_config('warn', foreground='#FFD700')    # Amarelo Ouro
        self.log_text.tag_config('info', foreground='#00BFFF')    # Azul Claro
        self.log_text.tag_config('process', foreground='#E0E0E0') # Cinza Claro
        self.log_internal("Pronto. O download será executado simultaneamente.", 'info')

    # --- Funções de Log e Utilidade (Atualizadas para cor) ---
    def log_internal(self, message, level='process'):
        """Adiciona uma mensagem ao console de log e aplica a cor (somente thread principal)."""
        self.log_text.config(state='normal')
        
        # Adiciona a mensagem com a tag de cor
        self.log_text.insert(tk.END, message + "\n", level)
        
        self.log_text.see(tk.END) # Scroll para o final
        self.log_text.config(state='disabled')
        self.master.update()

    def log_message(self, message, level='process'):
        """Thread-safe: Agenda a atualização do log na thread principal."""
        self.master.after(0, self.log_internal, message, level)

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
        """Atualiza o texto de progresso geral."""
        completed = int(self.progress_count.get())
        if total > 0:
            self.progress_text_var.set(f"Progresso do Lote: {completed} de {total} itens concluídos.")
        else:
            self.progress_text_var.set("")
            
    # --- Criação dos Widgets (AGORA RESPONSIVO COM GRID) ---
    def create_widgets(self):
        BACKGROUND_DARK = '#212121'
        FOREGROUND_LIGHT = '#F0F0F0'
        LOG_BG = '#121212'
        
        # Frame principal que preenche a janela
        main_frame = ttk.Frame(self.master, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky='nsew')

        # Configura o redimensionamento da janela principal
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Configura a coluna 0 do main_frame para expandir horizontalmente
        main_frame.grid_columnconfigure(0, weight=1)

        # Título (Linha 0)
        title_label = ttk.Label(main_frame, text="🎵 Downloader de YouTube para MP3 em Lote", style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky='n', pady=(0, 15))
        
        # --- Seleção de Diretório de Saída (Linha 1) ---
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=0, sticky='ew', pady=5)
        path_frame.grid_columnconfigure(1, weight=1) # Coluna da Entry expande
        
        ttk.Label(path_frame, text="Salvar em:", anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        
        # CORREÇÃO DO ERRO: Removido 'ipady=4' do construtor tk.Entry, pois não é uma opção válida aqui.
        dir_entry = tk.Entry(path_frame, textvariable=self.output_dir_var, state='readonly', width=55, 
                             bg='#333333', fg=FOREGROUND_LIGHT, bd=0, relief=tk.FLAT,
                             readonlybackground='#333333', disabledforeground=FOREGROUND_LIGHT)
        
        # CORREÇÃO DO ERRO: Aplicado 'ipady' no método pack, que é o lugar correto para ele.
        dir_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=5, ipady=4)
        
        ttk.Button(path_frame, text="📁 Procurar...", command=self.select_output_directory).pack(side=tk.RIGHT)
        
        # --- Configuração de Qualidade (Linha 2) ---
        config_frame = ttk.Frame(main_frame)
        config_frame.grid(row=2, column=0, sticky='w', pady=5)
        
        ttk.Label(config_frame, text="Qualidade MP3:", anchor='w').pack(side=tk.LEFT, padx=(0, 5))
        
        quality_options = ['0 (320 kbps - Melhor)', '5 (192 kbps - Padrão)', '10 (128 kbps - Econômico)']
        self.quality_combobox = ttk.Combobox(config_frame, textvariable=self.audio_quality_var, values=quality_options, state='readonly', width=30, style='Dark.TCombobox')
        self.quality_combobox.pack(side=tk.LEFT)
        self.quality_combobox.current(0)

        # --- Entrada de URLs Label (Linha 3) ---
        ttk.Label(main_frame, text="🔗 Cole as URLs dos vídeos/playlists (uma por linha):", anchor='w').grid(row=3, column=0, sticky='ew', pady=(10, 2))

        # Entrada de URLs Text Area (Linha 4 - Expansível)
        # Adicionado padding interno (padx/pady) para melhorar o visual
        self.url_text = scrolledtext.ScrolledText(main_frame, height=8, width=50, wrap=tk.WORD, font=("Arial", 10), 
                                                bg='#333333', fg=FOREGROUND_LIGHT, insertbackground=FOREGROUND_LIGHT, bd=0, padx=8, pady=8)
        self.url_text.grid(row=4, column=0, sticky='nsew', padx=0, pady=5)
        main_frame.grid_rowconfigure(4, weight=1) # Permite que a área de URL se expanda

        # --- Feedback de Otimização (Linha 5) ---
        optimization_frame = ttk.Frame(main_frame)
        optimization_frame.grid(row=5, column=0, sticky='ew', pady=5)
        ttk.Label(optimization_frame, text="⚡ Otimização: Download simultâneo e 64 fragmentos concorrentes ativados.", 
                  foreground='#FFD700', background='#444444', padding="5").pack(fill='x')


        # --- Botão de Download (Linha 6) ---
        self.download_button = ttk.Button(main_frame, text="🚀 Iniciar Download & Conversão para MP3", 
                                          command=self.start_download_thread, 
                                          style='Download.TButton')
        self.download_button.grid(row=6, column=0, sticky='ew', pady=15, padx=0)

        # --- Log de Status Label (Linha 7) ---
        ttk.Label(main_frame, text="Status do Processo:", anchor='w').grid(row=7, column=0, sticky='ew', pady=(5, 2))
        
        # Progressbar (Linha 8)
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal', mode='determinate', 
                                            style="Red.Horizontal.TProgressbar", variable=self.progress_count)
        self.progress_bar.grid(row=8, column=0, sticky='ew', padx=0, pady=2)
        
        # Texto de Progresso Detalhado (Linha 9)
        ttk.Label(main_frame, textvariable=self.progress_text_var, anchor='w', foreground='#909090').grid(row=9, column=0, sticky='w', pady=(2, 5))
        
        # Log Console (Linha 10 - Expansível)
        # Adicionado padding interno (padx/pady) para melhorar o visual
        self.log_text = scrolledtext.ScrolledText(main_frame, height=8, width=50, wrap=tk.WORD, font=("Consolas", 9), 
                                                state='disabled', bg=LOG_BG, fg='#E0E0E0', bd=0, padx=10, pady=10)
        self.log_text.grid(row=10, column=0, sticky='nsew', padx=0, pady=5)
        main_frame.grid_rowconfigure(10, weight=1) # Permite que a área de Log se expanda


    # --- Funções de Processamento (Sem alterações na lógica) ---
    def start_download_thread(self):
        urls = self.url_text.get(1.0, tk.END).strip()
        url_list = urls.splitlines()
        url_list = [url.strip() for url in url_list if url.strip()]
        
        if not url_list:
            messagebox.showerror("Erro", "Por favor, cole pelo menos uma URL de vídeo ou playlist.")
            return

        self.download_button.config(state='disabled', text="Processando itens...")
        
        # Configura o máximo da barra de progresso e reseta
        self.progress_bar.config(maximum=len(url_list))
        self.progress_count.set(0.0)
        self.update_progress_text(len(url_list))
        
        self.log_internal("-" * 40, 'warn')
        self.log_internal("Iniciando o processo de download em segundo plano...", 'warn')
        self.log_internal(f"Total de {len(url_list)} itens a serem processados.", 'info')
        self.log_internal("-" * 40, 'warn')

        download_orchestrator_thread = threading.Thread(target=self.orchestrate_downloads, args=(url_list,))
        download_orchestrator_thread.start()

    def download_single_url(self, url, output_dir, audio_quality_flag, total_items):
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
        
        try:
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                bufsize=1
            )

            # Log em tempo real (Mantendo a cor de processo)
            for line in iter(process.stdout.readline, ''):
                self.log_message(line.strip(), 'process')

            process.stdout.close()
            return_code = process.wait()

            # Atualização do Progresso e Log Colorido
            self.master.after(0, self.progress_count.set, self.progress_count.get() + 1.0)
            self.master.after(0, self.update_progress_text, total_items)

            if return_code == 0:
                self.log_message(f"✅ [SUCESSO] Concluído: {url[:50]}...", 'success')
            else:
                self.log_message(f"❌ [AVISO] URL falhou com código {return_code}: {url[:50]}...", 'warn')
                
        except Exception as e:
            # Atualização do Progresso mesmo em caso de erro fatal
            self.master.after(0, self.progress_count.set, self.progress_count.get() + 1.0)
            self.master.after(0, self.update_progress_text, total_items)
            self.log_message(f"🚨 [ERRO FATAL] Falha em {url[:50]}: {e}", 'error')
            
    def orchestrate_downloads(self, url_list):
        output_dir = self.output_dir_var.get()
        audio_quality_flag = self.get_audio_quality_flag()
        total_items = len(url_list)
        
        os.makedirs(output_dir, exist_ok=True)
        self.log_message(f"Iniciando {total_items} downloads simultaneamente.", 'info')
        
        worker_threads = []
        
        for url in url_list:
            # Passa o número total de itens para o controle de progresso
            thread = threading.Thread(target=self.download_single_url, 
                                      args=(url, output_dir, audio_quality_flag, total_items))
            worker_threads.append(thread)
            thread.start()
            
        # Aguarda a conclusão de todas as threads
        for thread in worker_threads:
            thread.join()
            
        self.log_message("=" * 40, 'warn')
        self.log_message("🎉 PROCESSO DE LOTE CONCLUÍDO.", 'success')
        self.log_message("=" * 40, 'warn')
        
        # Retorna o estado da UI para o normal
        self.master.after(0, self.download_button.config, 
                          {'state': 'normal', 'text': "🚀 Iniciar Download & Conversão para MP3"})


if __name__ == '__main__':
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()