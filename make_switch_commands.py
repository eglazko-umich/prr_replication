# Make Switch Commands
# Rather than manually designing 14 switch tables I'm going to do them programmatically.
import json

ingress_switch = [1]
egress_switch = [14]
layer_1 = [2, 3, 4, 5]
layer_2 = [6, 7, 8, 9]
layer_3 = [10, 11, 12, 13]

runtime_dir = "./sx-commands/"

layers = [ingress_switch,
		  layer_1,
		  layer_2,
		  layer_3,
		  egress_switch]

p4_file = "prr.p4"
dir_name = "prr_replication"

def get_mac_addr(current_switch, next_switch):
	mac = "08:00:00:{}:{}:00"
	curr_num = str(current_switch)
	next_num = str(next_switch)
	if current_switch < 10:
		curr_num = '0' + curr_num

	if next_switch < 10:
		next_num = '0' + next_num

	return mac.format(curr_num, next_num)

# dest_set should be 1 or 6 for back and fwd respective
# Base should be 1 or 5 for the same ones.
def get_ecmp_grouping(dest_set, successors, base, switch_id):
	out_obj = {}

	out_obj["table"] = "MyIngress.ipv4_lpm"
	match_obj = {}
	ip4_addr = ["10.0.{}.0".format(str(dest_set)), 24]
	match_obj["hdr.ipv4.dstAddr"] = ip4_addr
	out_obj["match"] = match_obj

	out_obj["action_name"] = "MyIngress.set_prr_select"
	actions_obj = {}
	actions_obj["ecmp_base"] = base
	actions_obj["ecmp_count"] = len(successors)
	actions_obj["switch_id"] = switch_id
	out_obj["action_params"] = actions_obj
	return out_obj

# Base should be 1 for backwards, 5 for forwards
def get_nexthops(current_switch, successors, base):
	outlines = []

	for dest_ind in range(len(successors)):
		hop_obj = {}
		hop_obj["table"] = "MyIngress.prr_nhop"
		match_obj = {}
		match_obj["meta.prr_hash"] = dest_ind + base
		hop_obj["match"] = match_obj

		hop_obj["action_name"] = "MyIngress.set_nhop"
		action_obj = {}
		action_obj["dstAddr"] = get_mac_addr(current_switch, successors[dest_ind])
		action_obj["port"] = dest_ind + base
		hop_obj["action_params"] = action_obj
		outlines.append(hop_obj)

	return outlines


def get_ingress_hosts_nhops():
	dmac = "00:00:0a:00:01:01"
	daddr = "10.0.1.1"

	host_obj = {}
	host_obj["table"] = "MyIngress.ipv4_lpm"

	match_obj = {}
	match_obj["hdr.ipv4.dstAddr"] = [daddr, 32]
	host_obj["match"] = match_obj

	host_obj["action_name"] = "MyIngress.set_nhop"
	action_obj = {}
	action_obj["dstAddr"] = dmac
	action_obj["port"] = 1
	host_obj["action_params"] = action_obj
	return host_obj

def get_egress_hosts_nhops():
	dmac = "00:00:0a:00:06:02"
	daddr = "10.0.6.2"

	host_obj = {}
	host_obj["table"] = "MyIngress.ipv4_lpm"

	match_obj = {}
	match_obj["hdr.ipv4.dstAddr"] = [daddr, 32]
	host_obj["match"] = match_obj

	host_obj["action_name"] = "MyIngress.set_nhop"
	action_obj = {}
	action_obj["dstAddr"] = dmac
	action_obj["port"] = 5
	host_obj["action_params"] = action_obj
	
	return host_obj

headers = []
headers.append('{')
headers.append('\t"target": "bmv2",')
headers.append('\t"p4info": build/{}.p4info.txtpb",')
headers.append('\t"bmv2_json": "build/prr.json",')

for sw_set in range(len(layers)):
	for sw_ind in range(len(layers[sw_set])):
		full_obj = {}
		full_obj["target"] = "bmv2"
		full_obj["p4info"] = "build/{}.p4info.txtpb".format(p4_file)
		full_obj["bmv2_json"] = "build/prr.json"

		table_entries = []
		# Ingress and egress need last leg host distribution, not ecmp
		if sw_set == 0 :
			host = get_ingress_hosts_nhops()
			ecmp_2 = get_ecmp_grouping(6, layers[sw_set + 1], 5, layers[sw_set][sw_ind])
			fwd_hops = get_nexthops(layers[sw_set][sw_ind], layers[sw_set + 1], 5)
			table_entries.append(host)
			table_entries.append(ecmp_2)
			for hop in fwd_hops:
				table_entries.append(hop)

		elif sw_set == 4:
			ecmp_1 = get_ecmp_grouping(1, layers[sw_set - 1], 1, layers[sw_set][sw_ind])
			host = get_egress_hosts_nhops()
			back_hops = get_nexthops(layers[sw_set][sw_ind], layers[sw_set - 1], 1)
			table_entries.append(host)
			table_entries.append(ecmp_1)
			for hop in back_hops:
				table_entries.append(hop)

		else:
			ecmp_1 = get_ecmp_grouping(1, layers[sw_set - 1], 1, layers[sw_set][sw_ind])
			ecmp_2 = get_ecmp_grouping(6, layers[sw_set + 1], len(layers[sw_set-1]) + 1, layers[sw_set][sw_ind])
			back_hops = get_nexthops(layers[sw_set][sw_ind], layers[sw_set - 1], 1)
			fwd_hops = get_nexthops(layers[sw_set][sw_ind], layers[sw_set + 1], len(layers[sw_set-1]) + 1)
			table_entries.append(ecmp_1)
			table_entries.append(ecmp_2)
			for x in back_hops:
				table_entries.append(x)
			for x in fwd_hops:
				table_entries.append(x)

		full_obj["table_entries"] = table_entries

		file_name = "s{}-runtime.json".format(layers[sw_set][sw_ind])
		file_path = runtime_dir + file_name
		with open(file_path, 'w') as f:
			f.write(json.dumps(full_obj, indent = 4))