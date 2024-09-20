### Um simples script para sincronizar músicas e vídeos de playlists do youtube (e ytmusic) localmente no pc.

## Como usar?
* Ter o python 3.8 ou superior já instalado e configurado no PATH (Caso não tenha você pode baixar [nesse link](<https://www.python.org/>) e não esqueça de marcar a última opção da primeira tela do instalador: Add python to the PATH).
* Baixe todo o conteudo desse repositório como zip [clicando aqui](https://github.com/zRitsu/youtube-playlist-sync/archive/refs/heads/main.zip)
* Extraia e em seguida execute o start_windows.bat (será criado alguns arquivos txt etc)
* Abra o arquivo playlists_links_audio.txt e nele você coloca os links das suas playlists pra download das músicas em cada linha e salve-o em seguida (no caso de download dos vídeos use o arquivo playlists_links_video.txt).
* Agora basta apenas executar o start_windows.bat pra sincronizar todas as músicas e vídeos de suas playlists (Não remova o id da playlist que está no nome do arquivo m3u). As playlists em formato m3u serão salvas por padrão na pasta ./playlists_audio e ./playlists_video (você também pode definir um diretorio diferente editando os arquivos playlists_audio_directory.txt e playists_video_directory.txt)

**Nota 1:** A cada execução do start_windows.bat será gerado novos arquivos m3u das playlist pra manter a mesma consistencia das playlists que estão no yt (alterações de nomes, ordem de vídeos, adição e remoção de vídeos etc).

**Nota 2:** Caso mova os arquivos m3u das playlists pra outra pasta, você terá que mover também a pasta .synced_playlist_data. 

## Preview:

* Teste de reprodução da playlist m3u no Daum Potplayer com miniatura ativada na lista (pode ser ativado via preferências -> Reprodução > Lista de reprodução e na opção "lista" escolha uma que tenha miniaturas). Nota: alguns outros players como o VLC também tem suporte a thumb.

[![dPmN641.md.png](https://iili.io/dPmN641.md.png)](https://freeimage.host/i/dPmN641)
