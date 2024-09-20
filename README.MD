### Um simples script para sincronizar músicas e vídeos de playlists do youtube (e ytmusic) localmente no pc.

## Como usar?
* Tenha o python 3.8 ou superior já instalado e configurado no PATH (Caso não tenha você pode baixar [nesse link](<https://www.python.org/>) e não esqueça de marcar a última opção da primeira tela do instalador: Add python to the PATH).
* Baixe todo o conteudo desse repositório como zip [clicando aqui](https://github.com/zRitsu/youtube-playlist-sync/archive/refs/heads/main.zip)
* Extraia e em seguida execute o start_windows.bat (será criado o arquivo playlists.txt)
* Abra o arquivo playlists_links_audio.txt e nele você coloca os links das suas playlists pra download das músicas em cada linha e salve-o em seguida (no caso de download dos vídeos use o arquivo playlists_links_video.txt).
* Agora basta apenas executar o start_windows.bat pra sincronizar todas as músicas e vídeos de suas playlists (Nota: Não remova o id da playlist que está no nome da pasta e nos arquivos de vídeos e músicas).

Nota: A cada execução do start_windows.bat será feito alterações nas pastas e arquivos da playlist pra manter a mesma consistencia da playlist que está no yt (alterações de nomes, ordem de vídeos, adição e remoção de vídeos etc).

## Previews:

* Arquivos de áudio com tag de info sobre o vídeo e thumb embutida

[![dPsRG24.md.png](https://iili.io/dPsRG24.md.png)](https://freeimage.host/i/dPsRG24)

* Potplayer com miniatura ativada na lista (pode ser ativado via preferências -> Reprodução > Lista de reprodução e na opção "lista" escolha uma que tenha miniaturas). Nota: alguns outros players como o VLC também tem suporte a thumb.

[![dPsluYG.md.png](https://iili.io/dPsluYG.md.png)](https://freeimage.host/i/dPsluYG)

* Arquivos de vídeo com tag e thumb do vídeo original embutido nos arquivos

[![dPsEJ49.md.png](https://iili.io/dPsEJ49.md.png)](https://freeimage.host/i/dPsEJ49)
