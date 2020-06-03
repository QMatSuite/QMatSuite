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

import com.consts.Constants.EnumCard;

public class Card extends InputSection{
	/**
	 * 
	 */
	private static final long serialVersionUID = -7515062976251781681L;
	private EnumCard cardEnum;
	public Card(EnumCard cardE) {
		super();
		boolRequired = false;
		cardEnum = cardE;
	}
//	@Override
//	public ContainerInputString toStringWrapper() {
//		if (!isEmpty() || boolRequired) {
//			String message = "&"+cardEnum.name()+" "+ options +" \n";
//			String strTmp;
//			Set<String> keys = parameterDict.keySet();
//	        for(String key: keys){
//	        	if (parameterDict.get(key).isExplicitWrite() || parameterDict.get(key).isRequired()) {
//	        		strTmp = parameterDict.get(key).toString();
//	        		if (strTmp==null) {}
//	        		else if (!strTmp.isEmpty()) {message = message+strTmp+"\n";}
//	        	}
//	        }
//	        return message+"/\n";
//		}
//		else return "";
//	}
	@Override
	public ContainerInputString toStringWrapper() {
		ContainerInputString ci = new ContainerInputString();
		if (!isEmpty() || boolRequired) {
			String strTmp;
			Set<String> keys = parameterDict.keySet();
			//only add "&" in front when not containing "body", i.e. "...=..." syntax
			if (!keys.contains("body")) {ci.appendInput("&");}
			
			ci.appendInput(cardEnum.name()+" "+ options +" \n");
	        for(String key: keys){
	        	if (parameterDict.get(key).isExplicitWrite() || parameterDict.get(key).isRequired()) {
	        		strTmp = parameterDict.get(key).toString();
	        		if (strTmp==null) {ci.appendLog(cardEnum.name()+"-"+key+": required but not set\n");}
	        		else if (!strTmp.isEmpty()) {ci.appendInput(strTmp+"\n");}
	        	}
	        }
	        ci.appendInput("/\n");
		}
		return ci;
	}
}
