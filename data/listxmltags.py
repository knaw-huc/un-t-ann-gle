import glob
import xml.etree.ElementTree as ET

allTags =[] 

for f in glob.glob("vangogh/let*"):
    xmlTree = ET.parse(f)
    tags = {elem.tag for elem in xmlTree.iter()}
    allTags.extend(tags)

tagSet = set(allTags)
for tag in sorted(tagSet):
    print(tag)
