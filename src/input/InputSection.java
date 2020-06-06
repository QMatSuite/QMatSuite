/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
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

import java.io.Serializable;
import java.util.LinkedHashMap;

public abstract class InputSection implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = -5978615968104371200L;
	
	protected LinkedHashMap<String, InputValue> parameterDict; 
	protected Boolean boolRequired=false;
	protected String options="";
	
	public InputSection() {
		parameterDict = new LinkedHashMap<String, InputValue>();
	}
	public String addParameter(String key, InputValue val) {
		parameterDict.put(key,val);
		return null;
	}
	public void setBoolRequired(Boolean br) {
		boolRequired = br;
	}
	public void setOptions(String st) {
		if(st!=null) options=st;
	}
	public void print() {
		System.out.println(toString());
	}
	public abstract ContainerInputString toStringWrapper();
	public Boolean containsKey(String key) {
		return parameterDict.containsKey(key);
	}
	public InputValue getValue(String key) {
		return parameterDict.get(key);
	}
	public boolean isEmpty() {
		if(parameterDict==null || parameterDict.size()==0) {return true;}
		if(parameterDict.size()==1 && parameterDict.containsKey("body")) {
			//if only contains body, check whether body is empty
			return ((InputValueString) parameterDict.get("body")).isEmpty();
		}
		else {
			return false;
		}
	}
}
