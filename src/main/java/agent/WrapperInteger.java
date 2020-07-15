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
package agent;

public class WrapperInteger extends WrapperClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = 834652343873610631L;
	private Integer value;
	final private Integer defaultValue;
	
	public WrapperInteger(Integer val) {
		defaultValue = val;
		value = val;
		enabled = false;
	}
	public WrapperInteger(Integer val,Boolean bl) {
		defaultValue = val;
		value = val;
		enabled = bl;
	}
	public Integer getValue() {
		return value;
	}
	public void setValue(Integer val) {
		value = val;
	}
	public Boolean equals(Integer vl) {
		return java.util.Objects.equals(vl, value);
	}
	@Override
	public boolean isNull() {
		return value==null;
	}
	public Integer resetDefault() {
		value = defaultValue;
		return defaultValue;
	}
	@Override
	public boolean isDefaultNull() {
		return defaultValue==null;
	}
	@Override
	public String getValueString() {
		if(value==null) {return "null";}
		return value.toString();
	}
}