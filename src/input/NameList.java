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
import java.util.Set;

import com.consts.Constants.EnumNameList;

public class NameList extends InputSection{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7707997872165494410L;
	private EnumNameList nameEnum;
	public NameList(EnumNameList nameE) {
		super();
		boolRequired = false;
		nameEnum = nameE;
	}
	@Override
	public ContainerInputString toStringWrapper() {
		ContainerInputString ci = new ContainerInputString();
		if (!isEmpty() || boolRequired) {
			ci.appendInput("&"+nameEnum.name()+" "+ options +" \n");
			String strTmp;
			Set<String> keys = parameterDict.keySet();
	        for(String key: keys){
	        	if (parameterDict.get(key).isExplicitWrite() || parameterDict.get(key).isRequired()) {
	        		strTmp = parameterDict.get(key).toString();
	        		if (strTmp==null) {ci.appendLog(nameEnum.name()+"-"+key+": required but not set\n");}
	        		else if (!strTmp.isEmpty()) {ci.appendInput(strTmp+"\n");}
	        	}
	        }
	        ci.appendInput("/\n");
		}
		return ci;
	}
	
}
