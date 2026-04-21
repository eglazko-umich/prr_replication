#!/usr/bin/env python3
import os
from time import sleep
import sys
import p4runtime_lib.bmv2
import p4runtime_lib.helper
import random

ingress_switch = [1]
egress_switch = [14]
layer_1 = [2, 3, 4, 5]
layer_2 = [6, 7, 8, 9]
layer_3 = [10, 11, 12, 13]

layers = [ingress_switch,
		  layer_1,
		  layer_2,
		  layer_3,
		  egress_switch]


repeat_tests = 20
test_set = [
	{
		'forward': [2, 3, 4]
	},
	{
		'forward': [5, 6, 7, 10, 12]
	},
	{
		'forward': [6, 8, 13]
	},
	{
		'forward': [2, 3, 6, 7, 11, 13]
	},
	{
		'forward': [6, 8, 10, 12, 13]
	},
	{
		'forward': [2, 4, 5, 6, 8, 13]
	}
]

test_duration = 40
test_separation = 10

def get_mac_addr(current_switch, next_switch):
	mac = "08:00:00:{}:{}:00"
	curr_num = str(current_switch)
	next_num = str(next_switch)
	if current_switch < 10:
		curr_num = '0' + curr_num

	if next_switch < 10:
		next_num = '0' + next_num

	return mac.format(curr_num, next_num)
def create_fwd_drop_rule(p4info_helper):
	rule = p4info_helper.buildTableEntry(
		table_name = "MyIngress.ipv4_lpm",
		match_fields = {
			"hdr.ipv4.dstAddr": ("10.0.6.2", 32)
		},
		action_name = "MyIngress.drop"
	)

	return rule

def create_back_drop_rule(p4info_helper):
	rule = p4info_helper.buildTableEntry(
		table_name = "MyIngress.ipv4_lpm",
		match_fields = {
			"hdr.ipv4.dstAddr": ("10.0.1.1", 32)
		},
		action_name = "MyIngress.drop"
	)

	return rule

# dest_set should be 1 or 6 for back and fwd respective
# Base should be 1 or 5 for the same ones.
def set_prr_hash(p4info_helper, sw, dest_set, successors, base, switch_id):
	entry = p4info_helper.buildTableEntry(
		table_name = "MyIngress.ipv4_lpm",
		match_fields = {
			"hdr.ipv4.dstAddr": ("10.0.{}.0".format(dest_set), 24)
		},
		action_name = "MyIngress.set_prr_select",
		action_params = {
			"ecmp_base": base,
			"ecmp_count": len(successors),
			"switch_id": switch_id
		}
	)
	sw.WriteTableEntry(entry)

def set_next_hops(p4info_helper, sw, successors, base, curr_switch):
	for dest_ind in range(len(successors)):
		entry = p4info_helper.buildTableEntry(
			table_name = "MyIngress.prr_nhop",
			match_fields = {
				"meta.prr_hash": dest_ind + base
			},
			action_name = "MyIngress.set_nhop",
			action_params = {
				"dstAddr": get_mac_addr(curr_switch, successors[dest_ind]),
				"port": dest_ind + base
			}
		)
		sw.WriteTableEntry(entry)

def add_ingress_host_nhop(p4info_helper, sw):
	entry = p4info_helper.buildTableEntry(
		table_name = "MyIngress.ipv4_lpm",
		match_fields = {
			"hdr.ipv4.dstAddr": ("10.0.1.1", 32)
		},
		action_name = "MyIngress.set_nhop",
		action_params = {
			'dstAddr': "00:00:0a:00:01:01",
			'port': 1
		}
	)
	sw.WriteTableEntry(entry)

def add_egress_host_nhop(p4info_helper, sw):
	entry = p4info_helper.buildTableEntry(
		table_name = "MyIngress.ipv4_lpm",
		match_fields = {
			"hdr.ipv4.dstAddr": ("10.0.6.2", 32)
		},
		action_name = "MyIngress.set_nhop",
		action_params = {
			'dstAddr': "00:00:0a:00:06:02",
			'port': 5
		}
	)
	sw.WriteTableEntry(entry)

def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.

    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # TODO For extra credit, you can use the p4info_helper to translate
            #      the IDs in the entry to names
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()

p4info_helper = p4runtime_lib.helper.P4InfoHelper("./build/prr.p4.p4info.txtpb")

sw_conns = {}

for layer_ind in range(len(layers)):
	for sw_ind in range(len(layers[layer_ind])):
		sw_num = layers[layer_ind][sw_ind]
		sw_name = 's' + str(sw_num)
		sw_addr = "127.0.0.1:{}".format(str(50050 + sw_num))
		print("Setting up switch {} ".format(sw_name))
		connection = p4runtime_lib.bmv2.Bmv2SwitchConnection(sw_name,
												   address=sw_addr,
												   device_id = sw_num - 1)
		connection.MasterArbitrationUpdate()
		connection.SetForwardingPipelineConfig(p4info = p4info_helper.p4info,
										  	  bmv2_json_file_path = "./build/prr.json")
		sw_conns[sw_num] = connection
		if sw_num == 1:
			add_ingress_host_nhop(p4info_helper, connection)
			set_prr_hash(p4info_helper, connection, 6, layer_1, 5, sw_num)
			set_next_hops(p4info_helper, connection, layer_1, 5, sw_num)
		elif sw_num == 14:
			add_egress_host_nhop(p4info_helper, connection)
			set_prr_hash(p4info_helper, connection, 1, layer_3, 1, sw_num)
			set_next_hops(p4info_helper, connection, layer_3, 1, sw_num)
		else:
			set_prr_hash(p4info_helper, connection, 1, layers[layer_ind - 1], 1, sw_num)
			set_prr_hash(p4info_helper, connection, 6, layers[layer_ind + 1], 5, sw_num)
			set_next_hops(p4info_helper, connection, layers[layer_ind - 1], 1, sw_num)
			set_next_hops(p4info_helper, connection, layers[layer_ind + 1], 5, sw_num)

forward_drop_rule = create_fwd_drop_rule(p4info_helper)
backward_drop_rule = create_back_drop_rule(p4info_helper)

test_runs = 0
test_count = 0
while True:
	for test in test_set:
		# Write rules to force-drop traffic
		print("Starting new test: {}".format(str(test['forward'])))
		for drop_list in test.keys():
			for sw_num in test[drop_list]:
				conn = sw_conns[sw_num]
				if drop_list == 'both':
					conn.WriteTableEntry(forward_drop_rule)
					conn.WriteTableEntry(backward_drop_rule)
				elif drop_list == 'forward':
					conn.WriteTableEntry(forward_drop_rule)
				elif drop_list == 'back':
					conn.WriteTableEntry(backward_drop_rule)

		# Sleep to allow nodes to search out new paths
		print("Sleeping {} seconds for test to run.".format(test_duration))
		sleep(test_duration)

		# Remove rules for dropping traffic
		print("Restoring switches.")
		for drop_list in test.keys():
			for sw_num in test[drop_list]:
				conn = sw_conns[sw_num]
				if drop_list == 'both':
					conn.DeleteTableEntry(forward_drop_rule)
					conn.DeleteTableEntry(backward_drop_rule)
				elif drop_list == 'forward':
					conn.DeleteTableEntry(forward_drop_rule)
				elif drop_list == 'back':
					conn.DeleteTableEntry(backward_drop_rule)

		# Sleep to allow any stragglers to settle and report
		print("Sleeping {} seconds after test.".format(test_separation))
		sleep(test_separation)

		# Gather logs for the given test.
#		file_list = os.listdir("test_logs")
#		with open("test_logs/test_results.txt", 'a') as f:
#			f.write("Test {}\n".format(test_count))
#			for file in file_list:
#				if file == "test_results.txt":
#					continue	
#				with open("test_logs/{}".format(file), 'r') as r:
#					for line in r:
#						f.write(line)
#						f.write('\n')
#			os.unlink("test_logs/" + file)
#			f.write('\n')
		test_count += 1

	test_runs = test_runs + 1
	if test_runs >= repeat_tests:
		break

#chosen_sw = p4runtime_lib.bmv2.Bmv2SwitchConnection('s1',
#												   address="127.0.0.1:50051",
#												   device_id = 0)
#
#print("Switch selected.")
#chosen_sw.MasterArbitrationUpdate()
#print("Switch master updated.")
#
#chosen_sw.SetForwardingPipelineConfig(p4info = p4info_helper.p4info,
#									  bmv2_json_file_path = "./build/prr.json")
#set_prr_hash(p4info_helper, chosen_sw, 6, layer_1, 5, 1)
#set_next_hops(p4info_helper, chosen_sw, 1, layer_1, 5)
#add_ingress_host_nhop(p4info_helper, chosen_sw)
#print("Config line set.")
#
#break_rule = create_drop_rule(p4info_helper)
#fix_rule = create_pass_rule(p4info_helper)
#print("Rules created.")
#
#chosen_sw.WriteTableEntry(break_rule)
#print("Switch broken.")
#
#sleep(5)
#
#readTableRules(p4info_helper, chosen_sw)
#
#chosen_sw.DeleteTableEntry(break_rule)
#print("Switch fixed.")
