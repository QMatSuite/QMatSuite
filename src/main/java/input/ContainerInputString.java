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
package input;

import com.consts.Constants.EnumStep;

public class ContainerInputString {
	public EnumStep stepName;
	public String input;
	public String log;
	public boolean boolEmpty;
	public String commandName;
	public boolean boolNoInputFile;//set to true if the input string is to be directly passed to the command line
	public boolean boolNoMpi;//set to true if the command cannot use mpirun
	public String overrideStdInOutStem = "";//set to non-empty to override custom stdin and stdout file name
	public ContainerInputString() {
		input = "";
		log = "";
		stepName = null;
		boolEmpty = true;
		commandName = "";
		boolNoInputFile = false;
		boolNoMpi = false;
		overrideStdInOutStem = "";
	}
	public void appendInput(String st) {
		input = input + st;
	}
	public void appendLog(String st) {
		log = log + st;
	}
	public void append(ContainerInputString ci) {
		input = input + ci.input;
		log = log + ci.log;
	}
	public String toString() {
		return "Run with: "+commandName+"\n"+
				(boolNoInputFile?"Direct command\n":"With input file\n")+
				(boolNoMpi?"No mpi\n":"Allow mpi\n")+
				(input.isEmpty()? "":"------Input file-----\n"+input)+
				(log.isEmpty()? "":"-------Warning-------\n"+log);
	}
	public boolean isEmpty() {
		//return (input.isEmpty()&&log.isEmpty());
		return boolEmpty;
	}
	
}
