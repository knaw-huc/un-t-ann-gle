rm republic-annotation-files.lst
for x in volume resolution session dateoccurrence entity page paragraph; do
  find /Users/bram/workspaces/republic/republic-untangle/out/[0-9]* -mtime -3 -iname "web_annotations-*-$x.json" >> republic-annotation-files.lst
done
