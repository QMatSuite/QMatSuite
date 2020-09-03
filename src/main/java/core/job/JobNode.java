/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package core.job;

import java.io.File;
import java.lang.reflect.Field;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Map;

import com.programconst.DefaultFileNamesQE;

import core.com.error.ShowAlert;
import core.com.programconst.ProgrammingConsts;
import javafx.scene.control.Alert.AlertType;


public class JobNode implements Runnable {

	private Process jobProcess;
	
	private String commandName;
	
	private String workingDir;
	
	private String stdInOutFileStem;
	
	private String mpiCommand;
	
	private ArrayList<String> commandArguments = null;
	
	private boolean boolNoInput=false;//if true, no stdin
	
	private int ompNumThreads = 0;
	
	public boolean boolWriteStdErr = true;
	
	public boolean boolStopWhenCrashFileDetected = true;
	
	public JobNode(String workingDir, String commandName) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = null;
		this.mpiCommand = "";
		commandArguments=null;
		boolNoInput=true;
	}
	public JobNode(String workingDir, ArrayList<String> commandArgument, boolean boolStopWhenCrashFileDetected) {
		//commandName must be full path + command
		this.commandName = "";
		this.workingDir = workingDir;
		this.stdInOutFileStem = null;
		this.mpiCommand = "";
		this.commandArguments=commandArgument;
		this.boolNoInput=true;
		this.boolStopWhenCrashFileDetected = boolStopWhenCrashFileDetected;
	}
	public JobNode(String workingDir, String commandName, String stdInOutFileStem) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = stdInOutFileStem;
		this.mpiCommand = "";
		commandArguments=null;
		boolNoInput=false;
	}
	public JobNode(String workingDir, String mpiCommand, String commandName, String stdInOutFileStem) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = stdInOutFileStem;
		this.mpiCommand = mpiCommand;
		commandArguments=null;
		boolNoInput=false;
	}
	public JobNode(String workingDir, String mpiCommand, String commandName, String stdInOutFileStem, ArrayList<String> commandArguments, boolean boolNoInput) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = stdInOutFileStem;
		this.mpiCommand = mpiCommand;
		this.commandArguments=commandArguments;
		this.boolNoInput = boolNoInput;
	}
	public JobNode(String workingDir, String mpiCommand, String commandName, String stdInOutFileStem, ArrayList<String> commandArguments, boolean boolNoInput, boolean boolWriteStdErr) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = stdInOutFileStem;
		this.mpiCommand = mpiCommand;
		this.commandArguments=commandArguments;
		this.boolNoInput = boolNoInput;
		this.boolWriteStdErr = boolWriteStdErr;
	}
	
	@Override
	public void run() {
		//System.out.println("shshs");
		
		if(workingDir==null){return;} // || stdInOutFileStem==null
		//not execute the command if there is a file called "CRASH" in the working directory
		if(boolStopWhenCrashFileDetected && new File(workingDir,DefaultFileNamesQE.crashFile).exists()) {return;}
		
		ProcessBuilder builder = null;
		boolean boolError = false;
		
		builder = new ProcessBuilder();
		Map<String, String> environment = builder.environment();
		ompNumThreads = JobManager.isBoolParallel()?JobManager.getOmpNumThreads():1;
	    environment.put("OMP_NUM_THREADS", Integer.toString(ompNumThreads));
	    
		builder.directory(new File(workingDir));
		
		//construct command list
		ArrayList<String> stringArr = new ArrayList<String>();
		if(!mpiCommand.isEmpty()) {
			stringArr.add(mpiCommand);stringArr.add("-np");stringArr.add(Integer.toString(JobManager.getMpirunNum()));
		}
		if(commandName!=null && !commandName.isEmpty()) {stringArr.add(commandName);}
		if(commandArguments!=null && !commandArguments.isEmpty()) {stringArr.addAll(commandArguments);}
		if(!boolNoInput && stdInOutFileStem!=null) {
			stringArr.add("-inp");stringArr.add(stdInOutFileStem + ProgrammingConsts.stdinExtension);
		}
		//add command list to the process
		builder.command(stringArr);
		
    	//builder.redirectInput(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stdinExtension));
		if(stdInOutFileStem!=null) {
			builder.redirectOutput(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stdoutExtension));
			if(boolWriteStdErr) {
				builder.redirectError(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stderrExtension));
			}
		}
		
        try {
            synchronized (this) {
                this.jobProcess = builder.start();
            }

            if (this.jobProcess != null) {
                if (this.jobProcess.waitFor() != 0) {
                	boolError = true;
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
            boolError = true;
        } finally {
            synchronized (this) {this.jobProcess = null;}
        }
		
	}
	public synchronized void stop() {
        if (this.jobProcess != null) {
        	
            //try to solve the mpirun won't stop problem in linux
            //ShowAlert.showAlert(AlertType.INFORMATION, "Debug", jobProcess.getClass().getName(),false);
            if(!mpiCommand.isEmpty() && "java.lang.UNIXProcess".equals(jobProcess.getClass().getName())) {
            	
	        	// get the PID on unix/linux systems
				try {
					Field f = jobProcess.getClass().getDeclaredField("pid");
					f.setAccessible(true);
					int pid = f.getInt(jobProcess);
					//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "pkill -P "+Integer.toString(pid),false);
					
					//kills all children of the current given process
					//Runtime.getRuntime().exec(new String[]{"bash","-c","pkill -P "+Integer.toString(pid)});
					Process p = Runtime.getRuntime().exec("pkill -P "+Integer.toString(pid));
					int intVal = p.waitFor();
					//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", ""+intVal,false);
					
					if(intVal!=0){
						//in case pkill is not available
						p = Runtime.getRuntime().exec("kill $(ps -o pid= --ppid "+pid+")");
						intVal = p.waitFor();
						if(intVal!=0){
							ShowAlert.showAlert(AlertType.WARNING, "Warning", 
						"The mpirun processes might not have been successfully terminated. Please check manually.");
						}
					}

				} catch (Throwable e) {
					e.printStackTrace();
				}
        	}
		this.jobProcess.destroy();
            
        }
    }
	public synchronized String getName() {
		String workName;
		try {
			workName = (new File(workingDir)).getParentFile().getName() +File.separator+ (new File(workingDir)).getName();
		}
		catch(Exception e) {
			workName = "Unknown.";
		}
		String strMpi = mpiCommand.isEmpty()?"":(Paths.get(mpiCommand).getFileName().toString()+" on "+JobManager.getMpirunNum()+" cores, ");
		strMpi+=(ompNumThreads==1?"":"openmp "+ompNumThreads+ " threads, ");
		String strQe = Paths.get(commandName).getFileName().toString();
        return strMpi+" "+strQe+" : step "+stdInOutFileStem+" from "+workName;
    }

}
