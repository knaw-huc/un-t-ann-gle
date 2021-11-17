from lxml import etree

def get_root_tree_element(filename):
	return etree.iterparse(filename, events=('start','end'))

def find_unique_contexts(filenames):
	unique_contexts = []
	for f in filenames:
		sax_events = get_root_tree_element(f)
		for action, elem in sax_events:
			parent = elem.getparent()
			parent_tag = parent.tag if parent is not None else None
			parent_attrib_keys = parent.attrib.keys() if parent is not None else None

			context = {
				'tag': elem.tag,
				'parent': parent_tag,
				'parent_attrib_keys': parent_attrib_keys
			}

			if not context in unique_contexts:
				unique_contexts.append(context)

	return unique_contexts
