import logging 
from netmiko import ConnectHandler 
from lib.utilities import * 
import re
from parsers.cisco import cisco_asr9910

# logger = logging.getLogger(__name__)
#----------------------------------------------------#
# PreCheck class
#----------------------------------------------------#
class PreCheck: 

    """
    Handles configuration and log backups from devices. 
    Currently support JUNOS devices

    """

    def __init__(self, device, accepted_vendors): 
         self.device = device
         self.accepted_vendors = accepted_vendors
         self.conn = None
         self.host = device.get("host")
         self.device_type = device.get('device_type')
         self.vendor = device.get('vendor')
         self.model = device.get('model')
         self.username = device.get('username')
         self.remote_server = device.get('remote_backup_server')
         self.remote_password = device.get('remote_password')
                  
    # -------------------------------
    # Connection Handling 
    # -------------------------------
    def connect(self, logger):
        try: 
            msg = f"Connecting to {self.host}"
            logger.info(msg)
            session_log_dir = os.path.join(os.getcwd(), "outputs")
            os.makedirs(session_log_dir, exist_ok=True)

            session_logs_file = f"{self.vendor}_{self.model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
            session_logs_path = os.path.join(session_log_dir, session_logs_file)
            if not self.conn:
                self.conn = login_device(
                    device_type = self.device.get('device_type'),
                    host = self.device.get("host"),
                    username = self.device.get("username"), 
                    password = self.device.get("password"),
                    session_log_path= session_logs_path,
                    logger = logger
                )
            
            msg = f"{self.host}: Connected successfully"
            logger.info(msg)
            return self.conn

        except Exception as e: 
            msg = f"{self.host}: Not able to connect the device for vendor: {self.vendor}"
            logger.error(msg)
            exit  

    def disconnect(self, logger): 
        try:
            print("--------------------connection getting disconnected-------------------" ,self.conn)
            if self.conn: 
                msg = "Logging out from device"
                logging.info(msg)
                logout_device(self.conn, self.host, logger)
                self.conn = None 
            else: 
                msg = "Device is not connected already"
                logger.info(msg)
                exit
        except Exception as e: 
            msg = "Not able to logout from device for vendor: {self.vendor}"
            logger.error(msg)
            exit



    #
    def validateFPDs(self, conn, logger, device_name):
        """
        Verify and upgrade Cisco FPDs using stored command output.
    
        Logic:
        - Skip Juniper devices
        - For Cisco, read 'show hw-module fpd' from device_results
        - Compare running vs programmed versions
        - Upgrade if versions differ
        """
    
        try:
            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
    
            if (self.vendor not in  self.accepted_vendors):
                    msg = f"Unsupported vendor: {self.vendor}"
                    logger.error(msg)
                    self.disconnect(logger)
                    raise ValueError(msg)
            
            logger.info("Starting Cisco FPD version verification...")
    
            #  Get stored output from device_results
            fpd_output = None
    
            for device_entry in global_variable.device_results:
                if device_name in device_entry:
                    commands = device_entry[device_name].get("pre", [])
                    for cmd in commands:
                        if cmd.get("command") == "show_hw-module_fpd":
                            fpd_output = cmd.get("output")
                            break
    
            if not fpd_output:
                logger.error("show hw-module fpd output not found in device_results")
                return False
    
            # Parse output using existing parser
            fpd_list = cisco_asr9910.show_hw_module_fpd(fpd_output)
    
            if not fpd_list:
                logger.warning("Parser returned no FPD data")
                return True
    
            upgrade_required = []
    
            #  Compare versions
            for fpd in fpd_list:
                location = fpd.get("location")
                fpd_name = fpd.get("fpd")
                running = fpd.get("running_version")
                programmed = fpd.get("programmed_version")
    
                if not fpd:
                    logger.warning(f"Skipping invalid entry: {fpd}")
                    continue
    
                # if not running or not programmed:
                #     logger.warning(f"Skipping {location} {fpd_name}: version info missing")
                #     continue
    
                if running.strip() != programmed.strip():
                    upgrade_required.append(fpd)
                    logger.warning(
                        f"Upgrade needed → {location} {fpd_name} \n"
                        f"(Running: {running}, Programmed: {programmed})"
                    )
                else:
                    logger.info(f"Up-to-date → {location} {fpd_name}")
    
            #  No upgrades needed
            if not upgrade_required:
                logger.info("All FPDs are up-to-date")
                return True
    
            logger.warning(f"{len(upgrade_required)} FPD(s) require upgrade")
    
            #  Perform upgrades
            for fpd in upgrade_required:
                location = fpd["location"]
                fpd_name = fpd["fpd"]
    
                cmd = f"upgrade hw-module location {location} fpd {fpd_name}"
                logger.info(f"Executing: {cmd}")
    
                conn.send_command(cmd, expect_string=r"#", read_timeout=600)
    
                logger.info(f"Upgrade triggered for {location} {fpd_name}")

            # ---- Reload device ----
            logger.info("Reloading device...")
            conn.send_command("reload", expect_string=r"Proceed with reload", read_timeout=10)
            conn.send_command("yes", expect_string=r"#", read_timeout=10)
            
            logger.info("Cisco FPD upgrade procedure completed")
            self.prechecks.disconnect(logger)
            return True
    
    
        except Exception as e:
            logger.error(f"FPD verification/upgrade failed: {str(e)}")
            self.prechecks.disconnect(logger)
            return False
    

    # -------------------------------
    # SCP function
    # -------------------------------
    
    def scpFile(self, conn, src, dest, logger): 
      """
      Copying files to remote server
      """
     
      try: 
        msg = f"Copying files to remote server" 
        print(msg) 
        logger.info(msg) 
        
        cmd = [
          "start shell",
          "\n"
          f"scp -C {src} {dest}", 
          "\n",
          self.remote_password,
          "\n",
          "exit",
          "\n"
        ]
        saving_file = conn.send_multiline_timing(cmd, read_timeout=0)
        logger.debug(f"{self.host}: SCP output:\n{saving_file}") 
        if "No such file or directory" in saving_file: 
          msg = f"{self.host}: No such file or directory: {src}"
          print(msg)
          return  False
        if not saving_file: 
          msg = f"{self.host}: Not able to save the file. Please look into to the SCPFile()"
          logger.info(msg) 
          print(msg) 
          return False 
        print("file copied")
        return True
      except Exception as e: 
        msg = f"{self.host}: scp failed for {self.vendor} due to {e}"
        logger.error(msg)
        print(msg) 
        return False

        

    # -------------------------------
    # Pre Backup image 
    # -------------------------------

    def preBackup(self,conn,filename, logger): 
        """
        Backup the running configuration 
        """

        try: 
            msg = f"Taking device backup vendor: {self.vendor}"
            print(f"Taking device backup vendor: {self.vendor}")
            logger.info(msg)

            if not conn: 
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
                            
            if (self.vendor not in  self.accepted_vendors):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)
         
            if self.vendor == "juniper": 
                preBackupConfig = False
                preDeviceLog = False

                # Step1: Backup of device running config
                config_commands = [
                    f"save {filename}", 
                    "run file list"
                ]
                configBackup = conn.send_config_set(config_commands, cmd_verify = False, strip_command = True)
                if configBackup:
                   print("copying config files")
                   src = f"/var/home/lab/{filename}"
                   dest = f"{self.remote_server}:/var/tmp/{filename}"
                   saveFile = self.scpFile(conn,src, dest, logger)
                   if saveFile:
                     preBackupConfig = True
                   else: 
                     self.disconnect(logger) 
                     return False

                # Step2: Backup of device log
                log_commands = [
                    f"request support information | save /var/log/{filename}.txt", 
                    f"file archive compress source /var/log/* destination /var/tmp/{filename}.tgz"
                ]

                for cmd in log_commands: 
                    logs = conn.send_command(cmd, cmd_verify = False, expect_string=r".*>", max_loops = 3, read_timeout = 300)
                if logs:
                  print("Copy log files")
                  src = f"/var/tmp/{filename}.tgz"
                  dest = f"{self.remote_server}:/var/tmp/{filename}.tgz"
                  #print("src,dest--------------------", src, dest)
                  saveFile = self.scpFile(conn,src, dest, logger)
                  #print("SAVING FILE---------------", saveFile)
                  if saveFile:
                    preDeviceLog = True
                  else:
                    self.disconnect(logger)
                    return False
                # Step3: Backing up the whole primary disk1 config to disk2
                preBackupDiskStatus = self.preBackupDisk(conn,logger)
                print("STATUS...............",preBackupConfig, preDeviceLog, preBackupDiskStatus)
                if(
                    not preBackupConfig 
                    or not preDeviceLog 
                    or not preBackupDiskStatus
                ): 
                    msg = f"Device Backup failed for vendor: {self.vendor}"
                    logger.error(msg)
                    self.disconnect(logger)
                    return False
            
            return True

        except Exception as e: 
            print(e)
            msg = f"Device Backup failed for vendor: {self.vendor}:  {e}"
            logger.error(msg)
            self.disconnect(logger)
            return False

    def preBackupDisk(self, conn,logger): 
        """
        Check number of disks on a device
        Backing up the whole primary disk1 config to disk2 for rollback
        """
        try: 
            msg = "Backing up the whole primary disk1 config to disk2 for rollback"
            logger.info(f"Backing up the whole primary disk1 config to disk2 for rollback for vendor: {self.vendor}")
            
            if not conn: 
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
            
            if (
                self.vendor not in  self.accepted_vendors
            ):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)

            if self.vendor == "juniper": 
                msg = f"Check number of disks on a juniper device "
                logger.info(msg)
                output = conn.send_command("show vmhost version", read_timeout=300)
                print(f"output: {output}")


                if "set b" in output and "set p" in output: 
                    msg = f"There are 2 disks in a device for vendor: {self.vendor}\n will take a backup of primary disk to backup disk"
                    logger.info(msg)
                    cmd = "request vmhost snapshot"
                    msg = f"{self.host}: executing the '{cmd}' for vendor: {self.vendor}"
                    logger.info(msg)
                    output = conn.send_command_timing(cmd)
                    if cmd in output or "yes,no" in output.lower(): 
                      output += conn.send_command("yes", expect_string=r".*>",  max_loops = 3, read_timeout=300)
                    print(f"snapshot output: {output}")
                    logger.info(f"{self.host}: Disk1 backup is done for {self.vendor}")
                else: 
                    msg = f"There is only 1 disk in  a device for {self.vendor}\n No need to take a disk backup"
                    logger.info(msg)
        
                return True
        except Exception as e: 
            msg = f"{self.host}: Disk backup failed for {self.vendor}: {e}"
            logger.error(msg)
            self.disconnect(logger)
            return False

    #---------------------
    # check storage space
    #---------------------
    
    def checkStorage(self,conn,min_disk_gb, logger):
        
        try:
            msg= f"{self.host}: Checking system storage for vendor: {self.vendor} "
            logger.info(msg)
            if not conn:
                msg="Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
                
            print(msg)
            if (
                self.vendor not in self.accepted_vendors
            ):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)
            print(msg)
            print("connection2", conn)
            storage_output = conn.send_command("show system storage", expect_string=r'.*>')
            print("command storage_output ::::", storage_output)
            
            avail_space=re.search(r"^/dev/gpt/var\s+\S+\s+\S+\s+(\S+)*", storage_output, re.M).group(1)
            print(avail_space)
            avail_space=avail_space[:-1]
            print(avail_space)
            avail_space=int(float(avail_space))
            print(avail_space,type(avail_space))

            if avail_space == None:
                msg= f"{self.host} Unable to parse storage output for vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)
                return False
 
            msg=f"{self.host}:  {avail_space} GB available for {self.vendor}"
            logger.info(msg)
 
            # Enough space
            if avail_space > min_disk_gb:
                msg= {"status": "OK", "avail_space": avail_space}
                logger.info(msg)
                print(msg)
                return True
 
            # ---------------------------------------------------
            # LOW STORAGE → START CLEANUP
            # ---------------------------------------------------
            msg="LOW STORAGE → START CLEANUP"
            logger.info(msg)
            logger.warning(f"{self.host}: Low space! Running system cleanup")
 
            # ---------------------------------------------------
            # Delete files from YAML
            # ---------------------------------------------------
            files_to_delete = self.device.get("cleanup_files")
            print(f"files to delete: {files_to_delete}")
 
            msg=f"{self.host} Delete files from YAML for vendor: {self.vendor}"
            logger.info(msg)
 
            if len(files_to_delete)==0:
                logger.error(
                    f"{self.host}: cleanup_files EMPTY -> No files are available to delete"
                )
                self.disconnect(logger)
                return False
 
            for file in files_to_delete:
                logger.info(f"{self.host}: Deleting {file}")
                conn.send_command(f"file delete {file}")
            
            msg = { "status": "SELECTED_FILES_DELETED" }
            logger.info(msg)
            print(msg)
            return True
        except Exception:
            msg = "f{self.host}: Storage cleanup failed for vendor: {self.vendor}"
            logger.exception(msg)
            self.disconnect(logger)
            raise
            return False
    # ------------------------------------
    # Transfering image to Router
    # -------------------------------------
    def transferImage(self,conn, image_path,target_image, logger):
        """
        Transfer JUNOS image to router disk (/tmp) using CLI commands
        (same style as deviceLog method)
        """
        try:
            msg="Transfer JUNOS image to router disk (/tmp) using CLI commands"
            logger.info(msg)
            print(msg)
            if not conn:
                msg="Not connected to device"
                print(msg)
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if (
                    self.vendor not in  self.accepted_vendors
                ):
                    msg = f"Unsupported vendor: {self.vendor}"
                    logger.error(msg)
                    self.disconnect(logger)
                    raise ValueError(msg)

            if self.vendor == "juniper":
                src = f"{self.remote_server}:{image_path}/{target_image}"
                dest = "/var/tmp/"
                image_transfer = self.scpFile(conn, src, dest, logger)
                if not image_transfer:
                  msg = f"{target_image} is not transfered to router"
                  logger.info(msg)
                  print(msg)
                  return False

            elif self.device_type == "cisco":
                pass

            msg = f"{self.host}: Image transferred to /var/tmp"
            logger.info(msg)
            print(msg)
            return True

        except Exception as e:
            msg=f"{self.host}: Image transfer failed: {e}"
            logger.error(msg)
            self.disconnect(logger)
            return False
            raise



    # -----------------------------------
    # Validate the MD5 Checksum of image
    # -----------------------------------
    
    def verifyChecksum(self,conn,checksum, target_image, logger):
        """
        Verify MD5 checksum of Junos image file in /var/tmp/
        Retrieves filename and expected checksum from self.device
        
        Returns:
            True if checksums match, False otherwise
        """
        try:
            msg=" Verify MD5 checksum of Junos image file"
            logger.info(msg)
            print(msg)
            if not conn:
                logger.error("Not connected to device")
                raise RuntimeError("Not connected to device")
            
            if (self.vendor not in self.accepted_vendors):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)
                
            if self.vendor =="juniper":
              filename = target_image
              expected_checksum = checksum
            
              if not filename or not expected_checksum:
                logger.error(f"{self.host}: Missing filename or checksum in device config")
                raise ValueError("Missing filename or checksum in device config")

              command = f"file checksum md5 /var/tmp/{filename}"
              logger.info(f"{self.host}: Executing '{command}'")
              output = conn.send_command(command, expect_string=r".*>", read_timeout=60)
              logger.debug(f"{self.host}: Checksum output: {output}")
              checksum = re.search(r'\.tgz\)\s*=\s*(.*)',output).group(1)
              print(f"checksum: {checksum}")
              logger.info(f"{self.host}: inputed from user checksum: {expected_checksum}")
              logger.info(f"{self.host}: extracted from device  checksum: {checksum}")
            
              # Compare checksums
              if checksum == expected_checksum:
                logger.info(f"{self.host}: Checksum verification PASSED")
                return True
              else:
                logger.warning(f"{self.host}: Checksum verification FAILED")
                logger.warning(f"{self.host}: Expected: {expected_checksum}")
                logger.warning(f"{self.host}: Got: {checksum}")
                return False

        except Exception as e:
           logger.error(f"{self.host}: Checksum verification failed: {e}")
           self.disconnect(logger)
           raise



junos-vmhost-install-mx-x86-64-22.4R3.25.tgz
    #----------------------------
    # disable re-protect filter
    #----------------------------

    def disableReProtectFilter(self,conn,logger):
        """
        Removes RE protection firewall filter from loopback interface (lo0).
        show configuration | display set | match lo0.0
        set interfaces lo0 unit 0 family inet filter input PROTECT-RE-FILTER
        """
        try:
            if not conn:
                msg="Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
                
           
            if (
                self.vendor not in self.accepted_vendors
            ):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)
                       
            filter_commands = [
                "delete interfaces lo0.0 family inet filter",
                "commit"
            ] 
            
            print(filter_commands)

            for cmd in filter_commands:
                logger.info(f"{self.host}: Executing '{cmd}'")
                print(f"Executing '{cmd}'")
                output  = conn.send_config_set(cmd, cmd_verify=False) + "\n"
            
            if not output: 
              msg = f"{self.host}: Didn't get any output from the re-protect filter. please check the disableReProtectFilter()"
              logger.error(msg) 
              print(msg) 
              return False

            return True
        except Exception:
            logger.exception(f"{self.host}: Disable RE protect filter failed")
            return False
            raise


