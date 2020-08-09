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

import com.error.InvalidTypeException;

public class InputValueDouble extends InputValue {

	private final Double paraDefault;
	private Double paraNow;//only show up in generating input from agent
	
	public InputValueDouble(String name, Double para, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = para;
		paraNow = paraDefault;
	}
	public InputValueDouble(String name, Integer para, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = Double.valueOf(para);
		paraNow = paraDefault;
	}
	public InputValueDouble(String name, Boolean boolReq) {
		super(name, boolReq);
		paraDefault = null;
		paraNow = paraDefault;
	}
	public InputValueDouble(String name) {
		super(name, true);
		paraDefault = null;
		paraNow = paraDefault;
	}

	@Override
	public void setValueNow(Double valueNow) throws InvalidTypeException{	
		paraNow = valueNow;
	}
	
	@Override
	public void setValueNow(Integer valueNow) throws InvalidTypeException{	
		double valueNew = valueNow.doubleValue();
		paraNow = valueNew;
	}
	
	@Override
	public void setValueNow(String valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot convert from string to double");
	}
	
	@Override
	public void setValueNow(Boolean valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot convert from boolean to double");
	}
	
	@Override
	public void setValueNow() throws InvalidTypeException{
		paraNow = null;
	}
	public void multiply(double db) throws InvalidTypeException {
		setValueNow(getValueNow()*db);
	}
	public Double getValueNow() {
		return paraNow;
	}
	
	@Override
	public String toString(boolean debugbool) {
		if(debugbool) {
			return nameString+", "+paraDefault+", "+paraNow+", "+(boolRequired? "required":"optional")+", "+(explicitWrite? "write":"ignored");
			}
		else {
			if (paraNow!=null) return "body".equals(nameString)? ""+paraNow :nameString+"="+paraNow;
			else return null;
		}
	}
}
