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
package job;

import java.io.File;

import com.programconst.ProgrammingConsts;


public class JobNode implements Runnable {

	private Process jobProcess;
	
	private String commandName;
	
	private String workingDir;
	
	private String stdInOutFileStem;
	
	
	public JobNode(String workingDir, String commandName) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = null;
	}
	public JobNode(String workingDir, String commandName, String stdInOutFileStem) {
		//commandName must be full path + command
		this.commandName = commandName;
		this.workingDir = workingDir;
		this.stdInOutFileStem = stdInOutFileStem;
	}
	
	@Override
	public void run() {
		ProcessBuilder builder = null;
		boolean boolError = false;
		
		builder = new ProcessBuilder();
		if(workingDir!=null) {builder.directory(new File(workingDir));}
        builder.command(commandName);
        if(stdInOutFileStem!=null){
        	builder.redirectInput(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stdinExtension));
        	builder.redirectOutput(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stdoutExtension));
        	builder.redirectError(new File(workingDir,stdInOutFileStem + ProgrammingConsts.stderrExtension));
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
            this.jobProcess.destroy();
        }
    }
	public synchronized String getName() {
        return commandName;
    }

}
