from cloudshell.networking.generic_bootstrap import NetworkingGenericBootstrap
from cloudshell.networking.networking_resource_driver_interface import NetworkingResourceDriverInterface
from cloudshell.shell.core.driver_utils import GlobalLock
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface
from cloudshell.shell.core.context_utils import context_from_args, get_connectivity_context_attribute
from cisco_nxos_connectivity_operations_extension import CiscoNXOSConnectivityOperationsExtension
import cloudshell.networking.cisco.nxos.cisco_nxos_configuration as config
import driver_config_extension as config_extension
import inject


class CiscoNXOSDriverExtension(ResourceDriverInterface, NetworkingResourceDriverInterface, GlobalLock):
    def __init__(self):
        super(CiscoNXOSDriverExtension, self).__init__()
        self._operations = None
        bootstrap = NetworkingGenericBootstrap()
        bootstrap.add_config(config)
        bootstrap.add_config(config_extension)
        bootstrap.initialize()

    @context_from_args
    def initialize(self, context):
        """Initialize method
        :type context: cloudshell.shell.core.context.driver_context.InitCommandContext
        """

        return 'Finished initializing'

    def cleanup(self):
        pass

    @property
    def operations(self):
        return CiscoNXOSConnectivityOperationsExtension()

    @context_from_args
    def ApplyConnectivityChanges(self, context, request):
        # connectivity_operations = inject.instance('connectivity_operations')
        connectivity_operations = self.operations
        connectivity_operations.logger.info('Start applying connectivity changes, request is: {0}'.format(str(request)))
        response = connectivity_operations.apply_connectivity_changes(request)
        connectivity_operations.logger.info('Finished applying connectivity changes, responce is: {0}'.format(str(
            response)))
        connectivity_operations.logger.info('Apply Connectivity changes completed')
        return response

    @GlobalLock.lock
    @context_from_args
    def restore(self, context, path, config_type, restore_method, vrf=None):
        """Restore selected file to the provided destination

        :param path: source config file
        :param config_type: running or startup configs
        :param restore_method: append or override methods
        :param vrf: VRF management Name
        """

        configuration_operations = inject.instance('configuration_operations')
        response = configuration_operations.restore_configuration(source_file=path, restore_method=restore_method,
                                                                  config_type=config_type, vrf=vrf)
        configuration_operations.logger.info('Restore completed')
        configuration_operations.logger.info(response)

    @context_from_args
    def save(self, context, destination_host, source_filename, vrf=None):
        """Save selected file to the provided destination

        :param source_filename: source file, which will be saved
        :param destination_host: destination path where file will be saved
        :param vrf: VRF management Name
        """

        configuration_operations = inject.instance('configuration_operations')
        response = configuration_operations.save_configuration(destination_host, source_filename, vrf)
        configuration_operations.logger.info('Save completed')
        return response


    @context_from_args
    def get_inventory(self, context):
        """Return device structure with all standard attributes

        :return: response
        :rtype: string
        """

        autoload_operations = inject.instance("autoload_operations")
        response = autoload_operations.discover()
        autoload_operations.logger.info('Autoload completed')
        return response

    @GlobalLock.lock
    @context_from_args
    def update_firmware(self, context, remote_host, file_path):
        """Upload and updates firmware on the resource

        :param remote_host: path to tftp:// server where firmware file is stored
        :param file_path: firmware file name
        :return: result
        :rtype: string
        """

        firmware_operations = inject.instance("firmware_operations")
        response = firmware_operations.update_firmware(remote_host=remote_host, file_path=file_path)
        firmware_operations.logger.info(response)

    @context_from_args
    def send_custom_command(self, context, command):
        """Send custom command

        :return: result
        :rtype: string
        """

        send_command_operations = inject.instance("send_command_operations")
        response = send_command_operations.send_command(command=command)
        print response
        return response

    @context_from_args
    def send_custom_config_command(self, context, command):
        """Send custom command in configuration mode

        :return: result
        :rtype: string
        """
        send_command_operations = inject.instance("send_command_operations")
        result_str = send_command_operations.send_config_command(command=command)
        return result_str

    @context_from_args
    def shutdown(self, context):
        pass

    @context_from_args
    def create_port_channel(self, context, ports, dut_ports, stp_mode):
        connectivity_operations = self.operations
        connectivity_operations.logger.info('Creating Portchannel on {}'.format(ports))
        result_str = connectivity_operations.create_port_channel(context, dut_ports, stp_mode)
        return result_str

    @context_from_args
    def delete_port_channel(self, context, ports, portchannel_id):
        connectivity_operations = self.operations
        connectivity_operations.logger.info('Deleting Portchannel {}'.format(portchannel_id))
        result_str = connectivity_operations.delete_port_channel(portchannel_id)
        return result_str
