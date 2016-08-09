import inject
from collections import OrderedDict
import re

from cloudshell.networking.networking_utils import *
from cloudshell.networking.operations.connectivity_operations import ConnectivityOperations
from cloudshell.networking.cisco.command_templates.ethernet import ETHERNET_COMMANDS_TEMPLATES
from cloudshell.networking.cisco.command_templates.vlan import VLAN_COMMANDS_TEMPLATES
from cloudshell.networking.cisco.command_templates.cisco_interface import ENTER_INTERFACE_CONF_MODE
from cloudshell.cli.command_template.command_template_service import add_templates, get_commands_list
from cloudshell.shell.core.context_utils import get_resource_name
from cloudshell.networking.cisco.cisco_connectivity_operations import CiscoConnectivityOperations
from cloudshell.shell.core.context_utils import get_reservation_context_attribute


class CiscoNXOSConnectivityOperationsExtension(CiscoConnectivityOperations):
    def __init__(self, cli=None, logger=None, api=None, resource_name=None):
        super(CiscoNXOSConnectivityOperationsExtension, self).__init__(cli, logger, api, resource_name)
        try:
            self.resource_name = get_resource_name()
        except Exception:
            raise Exception('CiscoHandlerBase', 'ResourceName is empty or None')

    @property
    def context(self):
        return inject.instance('context')

    def add_vlan(self, vlan_range, port, port_mode, qnq, ctag):
        self.save_port_config(self.context, port)
        self.configure_interface_speed(self.context, port)
        self.configure_interface_mtu(self.context, port)
        output = CiscoConnectivityOperations.add_vlan(self, vlan_range, port, port_mode, qnq, ctag)
        return output

    def remove_vlan(self, vlan_range, port, port_mode):

        output = CiscoConnectivityOperations.remove_vlan(self, vlan_range, port, port_mode)
        self.restore_port_config(self.context, port)
        return output

    def configure_interface_speed(self, context, interfaces):
        logger = inject.instance('logger')
        reservation_id = get_reservation_context_attribute('reservation_id', context)

        # api = inject.instance('api')
        ports_list = interfaces.split(',')
        connectors = self.api.GetReservationDetails(reservation_id).ReservationDescription.Connectors

        for port in ports_list:
            # Generate port name
            resource_map = self.api.GetResourceDetails(context.resource.name)
            port_full_name = self._get_resource_full_name(port, resource_map)
            port_name = port_full_name.split('/')[-1].replace('-', '/')

            if 'channel' in port_name.lower():
                port_name = port_name.replace('/', '-')

            try:
                conn_port = self.api.GetResourceDetails(port_full_name).Connections.FullPath
            except AttributeError:
                conn_port = self.api.GetResourceDetails(port_full_name).Connections[0].FullPath

            # Get speed from link attributes
            for connector in connectors:
                if connector.Source in conn_port or connector.Target in conn_port:
                    try:
                        speed = [attr.Value for attr in connector.Attributes if attr.Name == 'Link Speed'][0]
                    except IndexError:
                        speed = ''
                    break

            # Configure speed if not already configured
            if not re.search('^speed', (
                    self.cli.send_command('show running interface {}'.format(port_name))).lower()) and speed != '':
                self.cli.send_config_command('interface {}'.format(port_name))
                self.cli.send_config_command('speed {}'.format(speed))
            logger.info('Interface {0} was configured for speed {1}'.format(port_name, speed))

        return 'Interface Speed Configuration Completed'

    def configure_interface_mtu(self, context, interfaces):
        logger = inject.instance('logger')
        reservation_id = get_reservation_context_attribute('reservation_id', context)

        # No MTU configuration on NxOS
        if context.resource.model == 'Cisco NXOS Switch':
            logger.info('No Interface MTU Configuration for Nexus OS')
            return 'No Interface MTU Configuration for Nexus OS'

        # api = inject.instance('api')
        ports_list = interfaces.split(',')
        connectors = self.api.GetReservationDetails(reservation_id).ReservationDescription.Connectors

        for port in ports_list:
            # Generate port name
            resource_map = self.api.GetResourceDetails(context.resource.name)
            port_full_name = self._get_resource_full_name(port, resource_map)
            port_name = port_full_name.split('/')[-1].replace('-', '/')

            if 'channel' in port_name.lower():
                port_name = port_name.replace('/', '-')

            try:
                conn_port = self.api.GetResourceDetails(port_full_name).Connections.FullPath
            except AttributeError:
                conn_port = self.api.GetResourceDetails(port_full_name).Connections[0].FullPath

            # Get MTU from link attributes
            for connector in connectors:
                if connector.Source in conn_port or connector.Target in conn_port:
                    try:
                        mtu = [attr.Value for attr in connector.Attributes if attr.Name == 'Link MTU'][0]
                    except IndexError:
                        mtu = ''
                    break

            # Configure MTU if not already configured
            if not re.search('^mtu', (
            self.cli.send_command('show running interface {}'.format(port_name))).lower()) and mtu != '':
                self.cli.send_config_command('interface {}'.format(port_name))
                self.cli.send_config_command('mtu {}'.format(mtu))
            logger.info('Interface {0} was configured for MTU {1}'.format(port_name, mtu))

        return 'Interface MTU Configuration Completed'

    def save_port_config(self, context, ports):
        logger = inject.instance('logger')
        ports_list = ports.split(',')

        if len(ports_list) < 1:
            raise Exception('Port list is empty')

        # api = inject.instance('api')
        for port in ports_list:
            resource_map = self.api.GetResourceDetails(context.resource.name)
            temp_port_name = self._get_resource_full_name(port, resource_map)

            if '/' not in temp_port_name:
                logger.error('Interface was not found')
                raise Exception('Interface was not found')
            port_name = temp_port_name.split('/')[-1].replace('-', '/')
            if 'channel' in port_name.lower():
                port_name = port_name.replace('/', '-')

            speed = ''
            mtu = ''
            port_config = self.cli.send_command('show running-config interface {}'.format(port_name))
            mtu_r = re.search('mtu (\d+)', port_config)
            if mtu_r:
                mtu = mtu_r.group(1)

            speed_r = re.search('speed (\d+)', port_config)
            if speed_r:
                speed = speed_r.group(1)

            description = ';'.join(['speed={}'.format(speed), 'mtu={}'.format(mtu)])
            self.cli.send_config_command('interface {}'.format(port_name))
            self.cli.send_config_command('no shutdown')
            self.cli.send_config_command('description {}'.format(description))

        return 'Save port configuration complete'

    def restore_port_config(self, context, ports):
        logger = inject.instance('logger')
        ports_list = ports.split(',')

        if len(ports_list) < 1:
            raise Exception('Port list is empty')

        # api = inject.instance('api')
        for port in ports_list:
            resource_map = self.api.GetResourceDetails(context.resource.name)
            temp_port_name = self._get_resource_full_name(port, resource_map)

            if '/' not in temp_port_name:
                logger.error('Interface was not found')
                raise Exception('Interface was not found')
            port_name = temp_port_name.split('/')[-1].replace('-', '/')
            if 'channel' in port_name.lower():
                port_name = port_name.replace('/', '-')

            # Look for MTU and speed in description and put those values back to the interface
            port_config = self.cli.send_command('show running-config interface {}'.format(port_name))
            port_descr = re.search('description\s(.*)', port_config)

            self.cli.send_config_command('interface {}'.format(port_name))
            try:
                speed = re.search('speed=(.*?);', port_descr.group(0)).group(1)
            except AttributeError:
                self.cli.send_config_command('no speed')
            else:
                if speed == '':
                    self.cli.send_config_command('no speed')
                else:
                    self.cli.send_config_command('speed {}'.format(speed))

            try:
                mtu = re.search('mtu=(.*?)', port_descr.group(0)).group(1)
            except AttributeError:
                self.cli.send_config_command('no mtu')
            else:
                if mtu == '':
                    self.cli.send_config_command('no mtu')
                else:
                    self.cli.send_config_command('mtu {}'.format(mtu))

            self.cli.send_config_command('shutdown')
            self.cli.send_config_command('no description')

        return 'Restore port configuration complete'

    def create_port_channel(self, context, ports, stp_mode=''):
        # api = inject.instance('api')
        logger = inject.instance('logger')
        resource_details = context.resource
        reservation_id = get_reservation_context_attribute('reservation_id', context)
        existing_port_channels = list()
        port_channel_id = '0'
        dut_ports = ports.split(',')
        
        # Values for IOS
        max_port_chann = 65
        port_chann_str = 'Port-channel'

        # Values for NXOS
        if resource_details.model == 'Cisco NXOS Switch':
            max_port_chann = 4095
            port_chann_str = 'port-channel'

        # Get existing port-channels from switch
        port_channels = self.cli.send_command('show running-config | include {}'.format(port_chann_str))

        # Make a list of existing port channels on switch
        for line in port_channels.splitlines():
            if line.startswith('interface '):
                existing_port_channels.append(line.strip('interface {}'.format(port_chann_str)))

        # Find next available port channel on switch
        for port_chann in range(1, max_port_chann):
            if str(port_chann) not in existing_port_channels:
                port_channel_id = str(port_chann)
                break

        # Exit if all port channels are used up
        if port_channel_id == '0':
            logger.error('Could not find available port channel')
            raise Exception('could not find available port channel')

        # Create port channel on switch
        self.cli.send_config_command('interface port-channel {}'.format(port_channel_id))
        self.cli.send_config_command('switchport')
        if stp_mode.lower() == 'edge':
            self.cli.send_config_command('spanning-tree port type edge trunk')
        self.cli.send_config_command('description "{0}"'.format(reservation_id))
        logger.info('{0} was created'.format(port_channel_id))

        # Add interfaces to the new port channel
        exclude_list = list()
        for port in dut_ports:
            try:
                temp_port_name = self.api.GetResourceDetails(port).Connections.FullPath
            except AttributeError:
                try:
                    temp_port_name = self.api.GetResourceDetails(port).Connections[0].FullPath
                except:
                    exclude_list.append(port)
                    continue

            if '/' not in temp_port_name:
                logger.error('Interface was not found')
                raise Exception('Interface not found')

            port_name = temp_port_name.split('/')[-1].replace('-', '/')

            # If interface has a VLAN, cannot add to port-channel
            vlan_id = [line for line in
                       self.cli.send_command('show running interface {} | include vlan'.format(port_name)).splitlines()
                       if 'switchport' in line]

            if vlan_id:
                logger.info('Interface {0} has vlan, so cannot add to port-channel'.format(port_name))
                exclude_list.append(port_name)
                continue

            # Add ports to new port-channel
            self.cli.send_config_command('interface {}'.format(port_name))
            self.cli.send_config_command('no shutdown')
            self.cli.send_config_command('switchport')
            if resource_details.model == 'Cisco NXOS Switch':
                self.cli.send_config_command('channel-group {0} mode active'.format(port_channel_id))
            else:
                self.cli.send_config_command('channel-group {0} mode auto'.format(port_channel_id))
            if stp_mode == 'edge':
                self.cli.send_config_command('spanning-tree port type edge')
            logger.info('Interface {0} was added to channel-group {1}'.format(port_name, port_channel_id))

        logger.info('Port-Channel {} Configuration Completed, exiting create_port_channel'.format(port_channel_id))
        return 'Port-Channel {} Configuration Completed'.format(port_channel_id)

    def delete_port_channel(self, port_channel):
        logger = inject.instance('logger')

        port_channel_id = re.search('\d+', port_channel.split('/')[-1]).group(0)

        vlan_id = [line for line in self.cli.send_command(
            'show running-config interface port-channel {} | include vlan'.format(port_channel_id)).splitlines() if
                   re.search('switchport.*vlan.*\d+', line)]

        if vlan_id:
            self.cli.send_config_command('interface port-channel {}'.format(port_channel_id))
            self.cli.send_config_command('no {}'.format(vlan_id[0]))

        self.cli.send_config_command('interface port-channel {}'.format(port_channel_id))
        self.cli.send_config_command('no switchport')
        self.cli.send_config_command('shutdown')
        self.cli.send_config_command('no interface port-channel {}'.format(port_channel_id))
        logger.info('{0} was removed'.format(port_channel_id))

        logger.info('Port-Channel {} Configuration removed, exiting delete_port_channel'.format(port_channel_id))
        return 'Port-Channel {} Configuration Removed'.format(port_channel_id)
