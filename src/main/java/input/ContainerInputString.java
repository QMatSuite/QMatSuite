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
	public ContainerInputString() {
		input = "";
		log = "";
		stepName = null;
		boolEmpty = true;
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
		return (input.isEmpty()? "":"------Input file-----\n"+input)+
				(log.isEmpty()? "":"-------Warning-------\n"+log);
	}
	public boolean isEmpty() {
		//return (input.isEmpty()&&log.isEmpty());
		return boolEmpty;
	}
	
}
